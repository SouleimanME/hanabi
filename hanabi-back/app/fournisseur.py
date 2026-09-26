"""Accès au fournisseur de modèle de langue, partagé par l'assistant de fiche
et le conseiller cadeau.

Le fournisseur se choisit au déploiement : tout point d'accès au format « chat
completions » convient (REDACTION_URL, REDACTION_CLE, REDACTION_MODELE). Aucun
n'est nommé dans le code.
"""
import json
import urllib.error
import urllib.request

from pydantic import ValidationError

from .config import settings


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


def appeler(historique: list[dict], avec_image: bool = False, max_tokens: int = 2000) -> str:
    """Le texte de la réponse, ou une ErreurFournisseur qui dit quoi faire."""
    corps = {
        "model": settings.REDACTION_MODELE,
        "messages": historique,
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    try:
        reponse = transport(corps)
    except urllib.error.HTTPError as e:
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
