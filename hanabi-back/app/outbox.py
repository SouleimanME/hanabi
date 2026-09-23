"""File des courriels et tâche qui la vide.

Le message s'inscrit dans la transaction de la commande et part ensuite : une
panne du relais ne fait plus échouer un achat. Réessais espacés
exponentiellement, avec dispersion.

Une table suffit pour un seul processus web. À plusieurs instances, la prise de
lot demanderait `FOR UPDATE SKIP LOCKED` (voir `traiter_lot`).
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import SessionLocal
from .mailer import Courriel, envoyer

log = logging.getLogger("hanabi.outbox")


def deposer(db: Session, destinataire: str, sujet: str, texte: str, html: str | None = None) -> models.OutboxEmail:
    """Inscrit un courriel dans la file, sans commit : l'appelant valide avec la commande."""
    message = models.OutboxEmail(
        destinataire=destinataire, sujet=sujet, texte=texte, html=html
    )
    db.add(message)
    return message


def _prochain_delai(tentatives: int) -> timedelta:
    """1, 2, 4, 8, 16 minutes, à 20 % près pour ne pas repartir en rafale."""
    base = 60 * (2 ** max(0, tentatives - 1))
    return timedelta(seconds=base * random.uniform(0.8, 1.2))


def traiter_lot(db: Session, taille: int | None = None, maintenant: datetime | None = None) -> dict:
    """Remet les messages dus et rend le bilan. Appelable directement (tests)."""
    taille = taille or settings.OUTBOX_LOT
    maintenant = maintenant or datetime.now(timezone.utc)

    # À plusieurs instances : ajouter `.with_for_update(skip_locked=True)`
    messages = db.scalars(
        select(models.OutboxEmail)
        .where(
            models.OutboxEmail.statut == "en_attente",
            models.OutboxEmail.prochaine_tentative <= maintenant,
        )
        .order_by(models.OutboxEmail.prochaine_tentative)
        .limit(taille)
    ).all()

    bilan = {"envoyes": 0, "echecs": 0, "abandons": 0}

    for message in messages:
        message.tentatives += 1
        try:
            envoyer(
                Courriel(
                    destinataire=message.destinataire,
                    sujet=message.sujet,
                    texte=message.texte,
                    html=message.html,
                )
            )
        except Exception as erreur:  # noqa: BLE001 - toute panne de remise se traite pareil
            # Tronqué : certains relais répondent par des pages entières
            message.derniere_erreur = f"{type(erreur).__name__}: {erreur}"[:500]
            if message.tentatives >= settings.OUTBOX_TENTATIVES_MAX:
                message.statut = "abandonne"
                bilan["abandons"] += 1
                log.error(
                    "courriel abandonne",
                    extra={"id": message.id, "tentatives": message.tentatives,
                           "sujet": message.sujet, "erreur": message.derniere_erreur},
                )
            else:
                message.prochaine_tentative = maintenant + _prochain_delai(message.tentatives)
                bilan["echecs"] += 1
                log.warning(
                    "remise differee",
                    extra={"id": message.id, "tentatives": message.tentatives,
                           "erreur": message.derniere_erreur},
                )
        else:
            message.statut = "envoye"
            message.envoye_le = maintenant
            message.derniere_erreur = None
            bilan["envoyes"] += 1

    if messages:
        db.commit()
    return bilan


async def ouvrier(arret: asyncio.Event) -> None:
    """Vide la file en continu jusqu'à l'arrêt."""
    log.info("ouvrier outbox demarre", extra={"intervalle_s": settings.OUTBOX_INTERVALLE_SECONDES})
    while not arret.is_set():
        try:
            db = SessionLocal()
            try:
                # smtplib est bloquant : hors de la boucle d'événements
                bilan = await asyncio.to_thread(traiter_lot, db)
                if any(bilan.values()):
                    log.info("lot traite", extra=bilan)
            finally:
                db.close()
        except Exception:
            # Une erreur ne doit pas arrêter la boucle ; reprise au tour suivant
            log.exception("erreur de l'ouvrier outbox")

        try:
            # Attente interruptible pour ne pas retarder l'extinction
            await asyncio.wait_for(arret.wait(), timeout=settings.OUTBOX_INTERVALLE_SECONDES)
        except asyncio.TimeoutError:
            pass

    log.info("ouvrier outbox arrete")
