"""File d'attente des courriels, et tache qui la vide.

CE QUE CE MODULE RESOUT. Envoyer un courriel depuis la requete de commande coud
ensemble deux choses de fiabilite tres differente : une ecriture en base, qui
est transactionnelle, et un appel reseau vers un tiers, qui ne l'est pas. Les
deux pannes qui en decoulent sont symetriques et toutes deux mauvaises - soit
l'acheteur attend pendant que le relais rame, soit une panne du relais fait
echouer une commande deja payee.

Le message est donc INSCRIT dans la meme transaction que la commande, et remis
plus tard. S'il existe une commande, il existe un courriel : c'est la base qui
le garantit, pas un espoir. Le tunnel d'achat, lui, ne depend plus d'un tiers.

REESSAIS ESPACES EXPONENTIELLEMENT. Un relais indisponible le reste souvent
quelques minutes ; reessayer toutes les secondes ajoute de la charge sans rien
gagner, et retarde les messages valides coinces derriere. Les delais doublent
donc a chaque echec, avec une part d'aleatoire pour eviter que tous les messages
en attente ne repartent au meme instant - ce qui reconstituerait la rafale qu'on
cherche a etaler.

CE QUE CE N'EST PAS. Ce n'est pas Celery, ni une file de messages. Il n'y a
qu'un processus web, et une table suffit. Le jour ou il y en aurait deux, la
prise de lot devrait passer par un verrou (`FOR UPDATE SKIP LOCKED`), sans quoi
les deux instances enverraient les memes messages ; la fonction concernee le
signale a l'endroit exact ou la ligne serait a ajouter.
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
    """Inscrit un courriel dans la file, SANS valider la transaction.

    L'absence de `commit` est le coeur du motif, et non un oubli : l'appelant
    valide la commande et le courriel ensemble, ou ni l'un ni l'autre.
    """
    message = models.OutboxEmail(
        destinataire=destinataire, sujet=sujet, texte=texte, html=html
    )
    db.add(message)
    return message


def _prochain_delai(tentatives: int) -> timedelta:
    """Attente avant la prochaine tentative : 1, 2, 4, 8, 16 minutes."""
    base = 60 * (2 ** max(0, tentatives - 1))
    # Dispersion de 20 % : sans elle, cent messages tombes en meme temps
    # repartiraient ensemble et reconstitueraient la rafale.
    return timedelta(seconds=base * random.uniform(0.8, 1.2))


def traiter_lot(db: Session, taille: int | None = None, maintenant: datetime | None = None) -> dict:
    """Tente de remettre les messages dus. Rend le compte de ce qui a ete fait.

    Appelable directement, ce qui rend la remise testable sans horloge ni tache
    de fond - la suite de tests s'en sert pour rester deterministe.
    """
    taille = taille or settings.OUTBOX_LOT
    maintenant = maintenant or datetime.now(timezone.utc)

    # A plusieurs instances : `.with_for_update(skip_locked=True)` s'ajoute ici,
    # sinon deux ouvriers prendraient le meme lot.
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
            # Le texte de l'erreur est tronque : certains relais repondent par
            # des pages entieres, et un journal n'a pas a les stocker.
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
    """Vide la file en continu, jusqu'a ce qu'on demande l'arret."""
    log.info("ouvrier outbox demarre", extra={"intervalle_s": settings.OUTBOX_INTERVALLE_SECONDES})
    while not arret.is_set():
        try:
            db = SessionLocal()
            try:
                # `to_thread` : `smtplib` est bloquant, et l'appeler directement
                # figerait la boucle d'evenements - donc TOUT le service - le
                # temps que le relais reponde.
                bilan = await asyncio.to_thread(traiter_lot, db)
                if any(bilan.values()):
                    log.info("lot traite", extra=bilan)
            finally:
                db.close()
        except Exception:
            # Une panne de l'ouvrier ne doit jamais l'arreter : il reprendra au
            # tour suivant. C'est le seul `except` large du module, et il est ici
            # parce qu'une boucle de fond qui meurt en silence est pire que tout.
            log.exception("erreur de l'ouvrier outbox")

        try:
            # Attente interruptible : `sleep` seul retarderait l'extinction du
            # service de la duree de l'intervalle.
            await asyncio.wait_for(arret.wait(), timeout=settings.OUTBOX_INTERVALLE_SECONDES)
        except asyncio.TimeoutError:
            pass

    log.info("ouvrier outbox arrete")
