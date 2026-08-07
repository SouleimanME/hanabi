from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..pricing import validate_promo, _promo_label

router = APIRouter(prefix="/promos", tags=["promos"])


@router.post("/validate", response_model=schemas.PromoOut)
def check_promo(data: schemas.PromoCheckIn, db: Session = Depends(get_db)):
    """Valide un code sans l'appliquer. Leve 422 si invalide, expire ou minimum non atteint."""
    promo = validate_promo(db, data.code, data.subtotal_cents)
    return schemas.PromoOut(code=promo.code, kind=promo.kind, label=_promo_label(promo))
