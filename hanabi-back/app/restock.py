"""Retour en stock : prévient les personnes qui l'ont demandé sur la fiche.

Appelé quand le stock d'un produit épuisé remonte (réassort dans le
back-office, commande annulée). Un courriel par demande, puis la demande est
close : pas de relance, pas de liste de diffusion.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import emails, models, outbox
from .translations import localize

log = logging.getLogger("hanabi.retour_en_stock")


def signaler_retour(db: Session, produit: models.Product) -> int:
    """Met en file les courriels des alertes en attente et les clôt. Sans commit.

    Rend le nombre de personnes prévenues.
    """
    if not produit.active or produit.stock <= 0:
        return 0

    alertes = db.scalars(
        select(models.StockAlert).where(
            models.StockAlert.product_id == produit.id,
            models.StockAlert.notified.is_(False),
        )
    ).all()

    for alerte in alertes:
        # Nom de l'objet tel que la personne l'a lu sur la fiche
        nom, _ = localize(produit.code, alerte.lang, produit.name, produit.blurb)
        sujet, texte, html = emails.retour_en_stock(produit.id, nom, alerte.lang)
        outbox.deposer(db, alerte.email, sujet, texte, html)
        alerte.notified = True

    if alertes:
        log.info("retour en stock signale", extra={"produit": produit.code, "alertes": len(alertes)})
    return len(alertes)
