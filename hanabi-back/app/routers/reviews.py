from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..antibot import verify as verify_antibot
from ..analytics import REVENUE_STATUSES
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/products/{product_id}/reviews", tags=["reviews"])


@router.get("", response_model=list[schemas.ReviewOut])
def list_reviews(product_id: int, db: Session = Depends(get_db)):
    reviews = (
        db.query(models.Review)
        .filter(models.Review.product_id == product_id, models.Review.approved.is_(True))
        # Avis vérifiés (achat constaté) en premier
        .order_by(models.Review.verified.desc(), models.Review.created_at.desc())
        .all()
    )
    return reviews


@router.post("", response_model=schemas.ReviewOut, status_code=201)
def add_review(
    product_id: int,
    data: schemas.ReviewIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    verify_antibot(data.antibot, "review")

    product = db.get(models.Product, product_id)
    if product is None:
        raise HTTPException(404, "Produit introuvable.")

    # Achat constaté : une commande encaissée contient ce produit
    purchased = db.execute(
        select(models.Order.id)
        .join(models.OrderItem, models.OrderItem.order_id == models.Order.id)
        .where(
            models.Order.user_id == user.id,
            models.Order.status.in_(REVENUE_STATUSES),
            models.OrderItem.product_id == product_id,
        )
        .limit(1)
    ).first()

    # Tout client connecté peut donner un avis ; « vérifié » seulement après achat

    existing = (
        db.query(models.Review)
        .filter(models.Review.product_id == product_id, models.Review.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tu as déjà laissé un avis sur ce produit.")

    review = models.Review(
        product_id=product_id,
        user_id=user.id,
        author_name=user.name,
        rating=data.rating,
        text=data.text,
        verified=bool(purchased),
        approved=True,  # sans file de modération
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
