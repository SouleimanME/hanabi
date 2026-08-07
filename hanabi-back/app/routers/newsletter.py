"""Inscription aux annonces de series, et offre de bienvenue associee."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..antibot import verify as verify_antibot
from ..database import get_db
from ..ratelimit import limiter

router = APIRouter(prefix="/newsletter", tags=["newsletter"])

#: Code remis en echange de l'inscription. Il doit exister en base (voir
#: seed.py) : sa validite reelle est verifiee avant d'etre annoncee.
WELCOME_CODE = "BIENVENUE10"


def _welcome_code(db: Session) -> str | None:
    promo = db.query(models.Promo).filter(models.Promo.code == WELCOME_CODE).first()
    if promo is None or not promo.active:
        return None
    if promo.expires_at is not None and promo.expires_at < datetime.now(timezone.utc):
        return None
    return promo.code


@router.post("/subscribe", response_model=schemas.SubscribeOut, status_code=201)
@limiter.limit("5/minute")
def subscribe(request: Request, data: schemas.SubscribeIn, db: Session = Depends(get_db)):
    """Enregistre une adresse et renvoie le code de bienvenue.

    Formulaire ouvert, donc soumis aux memes barrieres que l'alerte de stock :
    sans elles, il sert a inscrire des tiers a leur insu et a inonder la base.

    Une adresse deja connue recoit le meme code sans erreur : lui repondre
    « deja inscrite » revelerait a un visiteur quelconque qu'une adresse
    donnee figure dans la base. Une reinscription apres desinscription est en
    revanche un nouveau consentement, et leve le drapeau.
    """
    verify_antibot(data.antibot, "subscribe")

    email = str(data.email).lower()
    existing = db.query(models.Subscriber).filter(models.Subscriber.email == email).first()
    if existing is None:
        db.add(models.Subscriber(email=email, lang=data.lang))
        db.commit()
    elif existing.unsubscribed:
        existing.unsubscribed = False
        existing.lang = data.lang
        db.commit()

    return schemas.SubscribeOut(ok=True, code=_welcome_code(db))
