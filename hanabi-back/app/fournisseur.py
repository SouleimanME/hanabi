"""Accès au fournisseur de modèle de langue, partagé par l'assistant de fiche
et le conseiller cadeau.

Le fournisseur se choisit au déploiement : tout point d'accès au format « chat
completions » convient (REDACTION_URL, REDACTION_CLE, REDACTION_MODELE). Aucun
n'est nommé dans le code.
"""
import json
import logging
import time
import urllib.error
import urllib.request

from pydantic import ValidationError

from .config import settings

log = logging.getLogger("hanabi.fournisseur")

class ErreurFournisseur(Exception):
    """Un échec, avec le statut HTTP à rendre et ce qu'il faut en dire."""

    def __init__(self, statut_http: int, message: str):
        super().__init__(message)
        self.statut_http = statut_http
        self.message = message


class ImageRefusee(Exception):
    """Le fournisseur refuse la requête qui porte une image."""


def configure() -> bool:
    return bool(settings.REDACTION_URL and settings.REDACTION_CLE and settings.REDACTION_MODELE)


def _envoyer(corps: dict) -> dict:
    """Un appel au fournisseur. Remplacé dans les tests."""
    requete = urllib.request.Request(
        settings.REDACTION_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(corps).encode(),
        headers={
            "Authorization": f"Bearer {settings.REDACTION_CLE}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(requete, timeout=settings.REDACTION_DELAI_SECONDES) as reponse:
        return json.loads(reponse.read())


transport = _envoyer

# Au-delà, mieux vaut dire au visiteur de réessayer que le faire attendre
ATTENTE_MAX_SECONDES = 10.0
dormir = time.sleep


def _envoyer_avec_patience(corps: dict) -> dict:
    """Un refus pour débit (429) est retenté une fois, après le délai demandé.

    Les offres d'entrée de gamme plafonnent à quelques requêtes par minute :
    deux visiteurs en même temps ne doivent pas faire une erreur.
    """
    try:
        return transport(corps)
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        try:
            attente = float(e.headers.get("Retry-After", 2)) if e.headers else 2.0
        except (TypeError, ValueError):
            attente = 2.0
        if attente > ATTENTE_MAX_SECONDES:
            raise
        dormir(max(attente, 0.5))
        return transport(corps)


def _motif(e: urllib.error.HTTPError) -> str:
    """Le corps d'un refus, qui dit quota, clé ou modèle ; jamais la demande."""
    try:
        return (e.read() or b"").decode("utf-8", "replace")[:300]
    except Exception:
        return ""


def appeler(
    historique: list[dict],
    avec_image: bool = False,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    modele: str | None = None,
) -> str:
    """Le texte de la réponse, ou une ErreurFournisseur qui dit quoi faire.

    `temperature` à 0 pour ce qui se vérifie (fiche, classement) : une même
    entrée rend la même sortie, et un écart mesuré n'est pas du hasard.
    """
    corps = {
        "model": modele or settings.REDACTION_MODELE,
        "messages": historique,
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        reponse = _envoyer_avec_patience(corps)
    except urllib.error.HTTPError as e:
        log.warning("le fournisseur refuse l'appel", extra={"statut": e.code, "motif": _motif(e)})
        if e.code in (400, 413, 415, 422) and avec_image:
            raise ImageRefusee from e
        if e.code in (401, 403):
            raise ErreurFournisseur(503, "Le fournisseur refuse la clé : vérifier REDACTION_CLE.") from e
        if e.code == 429:
            raise ErreurFournisseur(503, "Le fournisseur est saturé : réessayer dans une minute.") from e
        raise ErreurFournisseur(502, f"Le fournisseur a répondu {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErreurFournisseur(504, "Le fournisseur ne répond pas : réessayer plus tard.") from e
    try:
        contenu = reponse["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ErreurFournisseur(502, "Réponse du fournisseur illisible.") from e
    if isinstance(contenu, list):
        contenu = "".join(p.get("text", "") for p in contenu if isinstance(p, dict))
    return contenu or ""


def extraire_json(contenu: str) -> dict:
    """L'objet JSON de la réponse, même entouré de texte ou d'une clôture de code."""
    debut, fin = contenu.find("{"), contenu.rfind("}")
    if debut < 0 or fin < debut:
        raise ValueError("aucun objet JSON dans la réponse")
    donnees = json.loads(contenu[debut : fin + 1])
    if not isinstance(donnees, dict):
        raise ValueError("la réponse n'est pas un objet JSON")
    return donnees


def erreur_lisible(e: Exception) -> str:
    """Ce qu'on renvoie au modèle pour qu'il corrige sa réponse."""
    if isinstance(e, ValidationError):
        return "; ".join(f"{'.'.join(map(str, err['loc']))} : {err['msg']}" for err in e.errors()[:6])
    return str(e)
