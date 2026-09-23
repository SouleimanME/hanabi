"""Inscription à la lettre d'information, code de bienvenue et désinscription."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import abonnement, emails, models, outbox, schemas
from ..antibot import verify as verify_antibot
from ..database import get_db
from ..pii import masquer_email
from ..ratelimit import limiter

router = APIRouter(prefix="/newsletter", tags=["newsletter"])

#: Code de bienvenue, annoncé seulement s'il est actif en base (voir seed.py)
WELCOME_CODE = "BIENVENUE10"


def _welcome_code(db: Session) -> str | None:
    promo = db.query(models.Promo).filter(models.Promo.code == WELCOME_CODE).first()
    if promo is None or not promo.active:
        return None
    # SQLite relit les dates sans fuseau : comparer tel quel lèverait un TypeError
    if promo.expires_at is not None and models.as_utc(promo.expires_at) < datetime.now(timezone.utc):
        return None
    return promo.code


@router.post("/subscribe", response_model=schemas.SubscribeOut, status_code=201)
@limiter.limit("5/minute")
def subscribe(request: Request, data: schemas.SubscribeIn, db: Session = Depends(get_db)):
    """Enregistre une adresse et rend le code de bienvenue.

    Formulaire public, protégé par les barrières anti-robots. Une adresse connue
    reçoit la même réponse, pour ne rien révéler ; une réinscription après
    désinscription vaut nouveau consentement.
    """
    verify_antibot(data.antibot, "subscribe")

    email = data.email
    code = _welcome_code(db)

    inscription = (
        db.query(models.Subscriber).filter(func.lower(models.Subscriber.email) == email).first()
    )
    nouveau = inscription is None or inscription.unsubscribed

    if inscription is None:
        inscription = models.Subscriber(email=email, lang=data.lang)
        db.add(inscription)
        # Le numéro signe le lien de désinscription du courriel
        db.flush()
    elif inscription.unsubscribed:
        inscription.unsubscribed = False
        inscription.lang = data.lang

    # Courriel pour une nouvelle inscription seulement, sinon le formulaire
    # servirait à inonder une boîte ; même transaction que l'inscription
    if nouveau:
        sujet, texte, html = emails.bienvenue_newsletter(inscription.id, code, data.lang)
        outbox.deposer(db, email, sujet, texte, html)

    db.commit()

    # Code affiché tout de suite ; le courriel sert à le retrouver
    return schemas.SubscribeOut(ok=True, code=code)


@router.post("/unsubscribe")
@limiter.limit("10/minute")
def unsubscribe(request: Request, data: schemas.UnsubscribeIn, db: Session = Depends(get_db)):
    """Désinscription depuis le lien du courriel : la signature prouve la réception.

    La ligne reste, marquée : le retrait du consentement est lui-même une trace
    à conserver. Rend l'adresse masquée, pour que la page dise laquelle.
    """
    if not abonnement.signature_valide(data.id, data.signature):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ce lien de désinscription n'est pas valable. Écris-nous et nous retirerons l'adresse.",
        )

    inscrit = db.get(models.Subscriber, data.id)
    # Ligne effacée depuis (compte supprimé) : plus rien à désinscrire
    if inscrit is None:
        return {"ok": True, "deja": True, "email": None}
    deja = inscrit.unsubscribed
    if not deja:
        inscrit.unsubscribed = True
        db.commit()
    return {"ok": True, "deja": deja, "email": masquer_email(inscrit.email)}
