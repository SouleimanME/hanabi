"""Idempotence des requêtes qui ne doivent s'exécuter qu'une fois (en-tête `Idempotency-Key`).

Le client tire une clé avant d'envoyer et la répète en cas de réessai ; le
serveur rejoue la réponse enregistrée. Même convention que Stripe.

La clé s'insère d'emblée et la contrainte unique tranche : un SELECT préalable
laisserait passer les deux appels d'un double clic. Elle n'est pas liée au
compte (128 bits aléatoires), pour servir aussi aux invités.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .config import settings

log = logging.getLogger("hanabi.idempotence")

EN_TETE = "Idempotency-Key"

LONGUEUR_MIN = 8
LONGUEUR_MAX = 128


class Rejeu(Exception):
    """Requête déjà traitée, réponse connue."""

    def __init__(self, code: int, corps: str):
        super().__init__("rejeu")
        self.code = code
        self.corps = corps

    def reponse(self) -> Response:
        return Response(
            content=self.corps,
            status_code=self.code,
            media_type="application/json",
            # Distingue un rejeu d'une création au diagnostic
            headers={"Idempotent-Replay": "true"},
        )


def empreinte(charge: dict) -> str:
    """Empreinte stable du corps (`sort_keys` : l'ordre des clés ne compte pas)."""
    return hashlib.sha256(
        json.dumps(charge, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def valider(cle: str | None) -> str | None:
    """Contrôle la forme de la clé, facultative."""
    if cle is None:
        return None
    cle = cle.strip()
    if not cle:
        return None
    if not (LONGUEUR_MIN <= len(cle) <= LONGUEUR_MAX):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{EN_TETE} doit compter entre {LONGUEUR_MIN} et {LONGUEUR_MAX} caractères.",
        )
    if not all(c.isalnum() or c in "-_" for c in cle):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{EN_TETE} n'accepte que des lettres, chiffres, tirets et tirets bas.",
        )
    return cle


def reserver(db: Session, cle: str, point_entree: str, charge: dict) -> models.IdempotencyKey:
    """Prend la clé, ou lève `Rejeu` si elle est connue.

    @raises Rejeu: requête déjà traitée
    @raises HTTPException: clé réutilisée avec un autre corps (422), ou requête
        identique encore en cours (409)
    """
    signature = empreinte(charge)
    trace = models.IdempotencyKey(
        cle=cle, point_entree=point_entree, empreinte=signature, statut="en_cours"
    )
    db.add(trace)
    try:
        # flush : la contrainte s'applique, la transaction reste à l'appelant
        db.flush()
    except IntegrityError:
        db.rollback()
        return _resoudre_conflit(db, cle, point_entree, signature)
    return trace


def _resoudre_conflit(db: Session, cle: str, point_entree: str, signature: str) -> models.IdempotencyKey:
    """Statue sur une clé déjà prise."""
    existante = db.scalar(
        select(models.IdempotencyKey).where(
            models.IdempotencyKey.cle == cle,
            models.IdempotencyKey.point_entree == point_entree,
        )
    )
    if existante is None:
        # La ligne concurrente vient d'être annulée
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Requête concurrente en cours, réessaie dans un instant."
        )

    if existante.empreinte != signature:
        # Clé réutilisée : rendre la réponse d'un autre achat serait trompeur
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Cette {EN_TETE} a déjà servi pour une requête différente.",
        )

    if existante.statut == "en_cours":
        # 409 : attendre plutôt que relancer
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Une requête identique est en cours de traitement.",
        )

    log.info("rejeu servi", extra={"cle": cle, "point_entree": point_entree})
    raise Rejeu(existante.code_reponse or 200, existante.corps_reponse or "{}")


def conclure(db: Session, trace: models.IdempotencyKey, code: int, corps: str) -> None:
    """Enregistre la réponse produite."""
    trace.statut = "termine"
    trace.code_reponse = code
    trace.corps_reponse = corps


def purger(db: Session, maintenant: datetime | None = None) -> int:
    """Supprime les clés plus vieilles que la fenêtre de réessai ; rend le nombre de lignes."""
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = maintenant - timedelta(hours=settings.IDEMPOTENCE_RETENTION_HEURES)
    resultat = db.execute(
        delete(models.IdempotencyKey).where(models.IdempotencyKey.created_at < limite)
    )
    db.commit()
    return resultat.rowcount or 0
