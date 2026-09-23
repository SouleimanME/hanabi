from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..pricing import validate_promo, _promo_label
from ..ratelimit import limiter

router = APIRouter(prefix="/promos", tags=["promos"])


# Plafond propre : sans lui, la limite globale laissait essayer 200 codes par minute
@router.post("/validate", response_model=schemas.PromoOut)
@limiter.limit("20/minute")
def check_promo(request: Request, data: schemas.PromoCheckIn, db: Session = Depends(get_db)):
    """Valide un code sans l'appliquer ; 422 si invalide, expiré ou sous le minimum."""
    promo = validate_promo(db, data.code, data.subtotal_cents)
    return schemas.PromoOut(code=promo.code, kind=promo.kind, label=_promo_label(promo))
