"""Photos téléversées, servies à part du catalogue.

Une photo envoyée par le back-office arrive en `data:` (base64). Gardée telle
quelle dans la fiche, elle partait avec chaque liste de produits : 2,3 Mo pour
douze objets, rien en cache, et la grille attendait le tout. Elle est désormais
rangée dans `medias` sous l'empreinte de son contenu, et la fiche ne garde que
`/media/<empreinte>`.

L'adresse ne change que si le contenu change : la réponse se met en cache un an
(`immutable`). En sortie, l'API rend l'adresse complète, que l'interface affiche
comme n'importe quelle photo ; en entrée, elle reconnaît ses propres adresses et
les ramène au chemin court.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re
from contextvars import ContextVar

from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from . import models

PREFIXE = "/media/"
TYPES = {"image/png", "image/jpeg", "image/webp"}
# Une photo recadrée à 1 200 px pèse quelques centaines de kilo-octets
TAILLE_MAX = 4 * 1024 * 1024

_DATA = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$")
_CHEMIN = re.compile(r"^(?:https?://[^/]+)?/media/([0-9a-f]{64})$")

# Origine de la requête en cours, pour rendre des adresses complètes
_origine: ContextVar[str] = ContextVar("origine_medias", default="")


class OrigineDesMedias(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        jeton = _origine.set(str(request.base_url).rstrip("/"))
        try:
            return await call_next(request)
        finally:
            _origine.reset(jeton)


class PhotoInvalide(ValueError):
    pass


def ranger(db: Session, valeur: str) -> str:
    """Une photo `data:` devient `/media/<empreinte>` ; une adresse de ce serveur
    redevient son chemin court ; tout le reste (URL externe, blason) passe tel quel."""
    if not isinstance(valeur, str):
        return valeur
    chemin = _CHEMIN.match(valeur)
    if chemin:
        return PREFIXE + chemin.group(1)
    donnees = _DATA.match(valeur)
    if not donnees:
        if valeur.startswith("data:"):
            raise PhotoInvalide("Photo attendue en PNG, JPEG ou WebP.")
        return valeur
    try:
        octets = base64.b64decode(donnees.group(2), validate=False)
    except (binascii.Error, ValueError) as e:
        raise PhotoInvalide("Photo illisible.") from e
    if not octets or len(octets) > TAILLE_MAX:
        raise PhotoInvalide("Photo vide ou trop lourde (4 Mo au plus).")
    empreinte = hashlib.sha256(octets).hexdigest()
    if db.get(models.Media, empreinte) is None:
        db.add(models.Media(empreinte=empreinte, type=donnees.group(1), octets=octets))
        db.flush()
    return PREFIXE + empreinte


def publique(valeur: str) -> str:
    """`/media/<empreinte>` vers l'adresse complète de ce serveur."""
    if isinstance(valeur, str) and valeur.startswith(PREFIXE):
        return _origine.get() + valeur
    return valeur
