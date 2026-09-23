"""Mesure d'audience : durée pendant laquelle une consultation reste rattachée à un compte.

Le rattachement n'existe qu'avec l'accord du visiteur (bandeau cookies de la
boutique). Passé ce délai, la consultation reste comptée pour son produit et
son mois, sans plus désigner personne : les statistiques n'en ont pas besoin.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from . import models

# Durée recommandée par la CNIL pour les données de mesure d'audience
DUREE_RATTACHEMENT = timedelta(days=395)


def detacher_consultations_anciennes(db: Session, maintenant: datetime | None = None) -> int:
    """Retire le compte des consultations de plus de treize mois. Renvoie le nombre de lignes."""
    limite = (maintenant or datetime.now(timezone.utc)) - DUREE_RATTACHEMENT
    resultat = db.execute(
        update(models.ProductView)
        .where(models.ProductView.user_id.is_not(None), models.ProductView.created_at < limite)
        .values(user_id=None)
    )
    db.commit()
    return resultat.rowcount or 0
