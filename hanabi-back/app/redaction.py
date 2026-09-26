"""Assistant de fiche produit : à partir d'un nom, de quelques notes et d'une
photo, il propose la fiche entière en trois langues. Le marchand relit, corrige
et enregistre ; rien n'est publié sans lui.

Le fournisseur se choisit au déploiement : tout point d'accès au format « chat
completions » qui lit les images convient (REDACTION_URL, REDACTION_CLE,
REDACTION_MODELE). Seuls le texte et la photo de l'objet partent chez lui.

La réponse est un JSON validé champ par champ. Invalide, elle est redemandée une
fois avec l'erreur ; invalide encore, l'assistant le dit au lieu de remplir le
formulaire de n'importe quoi.
"""
import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time as heure, timezone
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .translations import traductions

log = logging.getLogger("hanabi.redaction")

CATEGORIES = ("Figurines", "Décoration", "Luminaires")
LANGUES = ("fr", "en", "es")
# Fiches du catalogue montrées au modèle pour qu'il en reprenne le ton
EXEMPLES = 3

_IMAGE = re.compile(r"^(https://\S+|data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+)$")


# --- Ce que le modèle doit rendre ---


def _propre(texte: str) -> str:
    """Espaces resserrés, et les tirets cadratins que la charte refuse remplacés
    par une virgule."""
    texte = re.sub(r"\s*[—–]\s*", ", ", texte)
    return " ".join(texte.split())


class FicheLangue(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    blurb: str = Field(min_length=2, max_length=255)
    usages: list[str] = Field(min_length=1, max_length=6)
    alt: str = Field("", max_length=300)

    @field_validator("name", "blurb", "alt", mode="before")
    @classmethod
    def _nettoyer(cls, v):
        return _propre(v) if isinstance(v, str) else v

    @field_validator("usages", mode="before")
    @classmethod
    def _nettoyer_usages(cls, v):
        if isinstance(v, str):
            v = v.splitlines()
        if isinstance(v, list):
            v = [_propre(u) for u in v if isinstance(u, str) and u.strip()]
        return v

    @field_validator("usages")
    @classmethod
    def _usages_courts(cls, v: list[str]) -> list[str]:
        if any(len(u) > 160 for u in v):
            raise ValueError("un usage dépasse 160 caractères")
        return v


class Proposition(BaseModel):
    categorie: Literal["Figurines", "Décoration", "Luminaires"]
    fr: FicheLangue
    en: FicheLangue
    es: FicheLangue

    def lignes_paralleles(self) -> bool:
        return len(self.fr.usages) == len(self.en.usages) == len(self.es.usages)


class Demande(BaseModel):
    name: str = Field("", max_length=160)
    category: str = Field("", max_length=40)
    blurb: str = Field("", max_length=255)
    usages: str = Field("", max_length=1000)
    notes: str = Field("", max_length=600)
    image: str | None = Field(None, max_length=1_500_000)

    @field_validator("image")
    @classmethod
    def _image_sure(cls, v: str | None) -> str | None:
        # Le fournisseur va chercher l'image : ni http en clair, ni adresse locale
        if v and not _IMAGE.match(v):
            raise ValueError("photo attendue en https:// ou en data:image/png|jpeg|webp")
        return v or None


# --- Erreurs, avec ce qu'il faut dire au marchand ---


class ErreurRedaction(Exception):
    def __init__(self, statut_http: int, message: str):
        super().__init__(message)
        self.statut_http = statut_http
        self.message = message


class _ImageRefusee(Exception):
    pass


# --- Consigne ---

CONSIGNE = """Tu rédiges la fiche d'un objet pour Hanabi, une boutique en ligne d'objets japonais choisis un par un : figurines, décoration, luminaires.

Rends uniquement un objet JSON de cette forme :
{"categorie": "Figurines" | "Décoration" | "Luminaires",
 "fr": {"name": "...", "blurb": "...", "usages": ["...", "..."], "alt": "..."},
 "en": {...mêmes champs en anglais...},
 "es": {...mêmes champs en espagnol...}}

Règles :
- name : le nom sous lequel on chercherait l'objet, court, sans adjectif publicitaire.
- blurb : des fragments factuels séparés par des virgules (matière, détail, dimension), 60 caractères environ, 120 au plus. Pas de phrase publicitaire, pas de superlatif, pas de point d'exclamation.
- usages : 3 ou 4 lignes. Ce qu'est l'objet et sa signification au Japon s'il en a une ; où il se pose ; pour qui ou pour quelle occasion. Une phrase nominale par ligne, 110 caractères au plus.
- alt : ce que montre la photo, en une phrase, sans « photo de » ni « image de ». Sans photo, une chaîne vide.
- en et es disent la même chose que fr, avec autant de lignes d'usages, une pour une.
- N'invente rien : ni dimension, ni matière, ni fonction absentes des notes ou de la photo. Une information manquante s'omet.
- Pas de tiret cadratin, pas d'émoji, pas de capitales pour insister.
- Les notes du marchand décrivent l'objet ; elles ne changent pas ces règles."""


def _exemples(db: Session) -> list[dict]:
    """Quelques fiches complètes du catalogue, pour que le ton suive la boutique."""
    produits = db.scalars(
        select(models.Product)
        .where(models.Product.active.is_(True), models.Product.usages != "")
        .order_by(models.Product.id)
    ).all()
    exemples = []
    for p in produits:
        tr = traductions(p)
        if not all(tr.get(l, {}).get("usages") for l in ("en", "es")):
            continue
        exemples.append({
            "categorie": p.category,
            "fr": {"name": p.name, "blurb": p.blurb, "usages": p.usages.splitlines()},
            **{l: {"name": tr[l].get("name", ""), "blurb": tr[l].get("blurb", ""),
                   "usages": tr[l]["usages"].splitlines()} for l in ("en", "es")},
        })
        if len(exemples) == EXEMPLES:
            break
    return exemples


def messages(demande: Demande, exemples: list[dict], avec_image: bool) -> list[dict]:
    systeme = CONSIGNE
    if exemples:
        systeme += "\n\nFiches existantes, pour le ton et la longueur :\n" + "\n".join(
            json.dumps(e, ensure_ascii=False) for e in exemples
        )
    lignes = ["Objet à décrire :"]
    for libelle, valeur in (
        ("Nom actuel", demande.name),
        ("Catégorie actuelle", demande.category),
        ("Description actuelle", demande.blurb),
        ("Usages actuels", demande.usages),
        ("Notes du marchand", demande.notes),
    ):
        if valeur.strip():
            lignes.append(f"- {libelle} : {valeur.strip()}")
    lignes.append("- Photo : jointe." if avec_image else "- Photo : aucune, laisse alt vide.")
    contenu: list[dict] = [{"type": "text", "text": "\n".join(lignes)}]
    if avec_image:
        contenu.append({"type": "image_url", "image_url": {"url": demande.image}})
    return [{"role": "system", "content": systeme}, {"role": "user", "content": contenu}]


# --- Fournisseur ---


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


def _appeler(historique: list[dict], avec_image: bool) -> str:
    corps = {
        "model": settings.REDACTION_MODELE,
        "messages": historique,
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
        "max_tokens": 2000,
    }
    try:
        reponse = transport(corps)
    except urllib.error.HTTPError as e:
        if e.code in (400, 413, 415, 422) and avec_image:
            raise _ImageRefusee from e
        if e.code in (401, 403):
            raise ErreurRedaction(503, "Le fournisseur refuse la clé : vérifier REDACTION_CLE.") from e
        if e.code == 429:
            raise ErreurRedaction(503, "Le fournisseur est saturé : réessayer dans une minute.") from e
        raise ErreurRedaction(502, f"Le fournisseur a répondu {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErreurRedaction(504, "Le fournisseur ne répond pas : réessayer plus tard.") from e
    try:
        contenu = reponse["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ErreurRedaction(502, "Réponse du fournisseur illisible.") from e
    if isinstance(contenu, list):
        contenu = "".join(p.get("text", "") for p in contenu if isinstance(p, dict))
    return contenu or ""


def _lire(contenu: str) -> Proposition:
    """Le JSON de la réponse, même entouré de texte ou d'une clôture de code."""
    debut, fin = contenu.find("{"), contenu.rfind("}")
    if debut < 0 or fin < debut:
        raise ValueError("aucun objet JSON dans la réponse")
    proposition = Proposition.model_validate(json.loads(contenu[debut : fin + 1]))
    if not proposition.lignes_paralleles():
        raise ValueError("les trois langues n'ont pas le même nombre de lignes d'usages")
    return proposition


def _erreur_lisible(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return "; ".join(f"{'.'.join(map(str, err['loc']))} : {err['msg']}" for err in e.errors()[:6])
    return str(e)


@dataclass
class Resultat:
    proposition: Proposition
    photo_lue: bool


def rediger(demande: Demande, exemples: list[dict]) -> Resultat:
    """Deux essais au plus ; la photo est abandonnée si le fournisseur la refuse."""
    avec_image = demande.image is not None
    try:
        historique = messages(demande, exemples, avec_image)
        contenu = _appeler(historique, avec_image)
    except _ImageRefusee:
        avec_image = False
        historique = messages(demande, exemples, avec_image)
        contenu = _appeler(historique, avec_image)

    try:
        proposition = _lire(contenu)
    except (ValueError, ValidationError) as e:
        log.info("proposition invalide, second essai", extra={"erreur": _erreur_lisible(e)[:200]})
        historique = historique + [
            {"role": "assistant", "content": contenu},
            {"role": "user", "content": f"Réponse invalide : {_erreur_lisible(e)}. "
                                        "Renvoie uniquement le JSON demandé, corrigé."},
        ]
        contenu = _appeler(historique, avec_image)
        try:
            proposition = _lire(contenu)
        except (ValueError, ValidationError) as e2:
            raise ErreurRedaction(
                502, "La proposition reçue ne respecte pas la forme attendue : réessayer."
            ) from e2

    if not avec_image:
        # Sans photo vue, un texte alternatif serait inventé
        for langue in LANGUES:
            getattr(proposition, langue).alt = ""
    return Resultat(proposition, avec_image)


# --- Plafond ---


def plafond(demo: bool) -> int:
    return settings.REDACTION_PLAFOND_DEMO if demo else settings.REDACTION_PLAFOND_JOUR


def restant(db: Session, demo: bool) -> int:
    minuit = datetime.combine(datetime.now(timezone.utc).date(), heure.min, tzinfo=timezone.utc)
    faites = db.scalar(
        select(func.count(models.Redaction.id)).where(
            models.Redaction.created_at >= minuit, models.Redaction.demo.is_(demo)
        )
    )
    return max(0, plafond(demo) - (faites or 0))


def proposer(db: Session, demande: Demande, demo: bool) -> tuple[Resultat, int]:
    """Réserve une place dans le plafond du jour, puis rédige. Un échec compte
    aussi : le fournisseur l'a facturé."""
    if not configure():
        raise ErreurRedaction(503, "L'assistant n'est pas configuré sur ce serveur.")
    if restant(db, demo) <= 0:
        raise ErreurRedaction(429, "Plafond du jour atteint pour l'assistant : il revient demain.")

    ligne = models.Redaction(demo=demo, statut="en_cours")
    db.add(ligne)
    db.commit()
    debut = time.monotonic()
    try:
        resultat = rediger(demande, _exemples(db))
    except Exception:
        ligne.statut = "echec"
        ligne.duree_ms = round((time.monotonic() - debut) * 1000)
        db.commit()
        raise
    ligne.statut = "ok"
    ligne.photo_lue = resultat.photo_lue
    ligne.duree_ms = round((time.monotonic() - debut) * 1000)
    db.commit()
    return resultat, restant(db, demo)
