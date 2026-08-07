import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, get_optional_user
from ..pricing import quote

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/quote", response_model=schemas.QuoteOut)
def get_quote(data: schemas.QuoteIn, db: Session = Depends(get_db)):
    """Recalcule le panier cote serveur (sous-total, remise, port, total)."""
    return quote(db, data.items, data.promo_code)


@router.post("/checkout", response_model=schemas.OrderOut, status_code=201)
def checkout(
    data: schemas.CheckoutIn,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    pricing = quote(db, data.items, data.promo_code)

    # --- Decrement de stock atomique, dans une transaction ---
    # UPDATE ... WHERE stock >= qty : si rowcount == 0, le stock etait insuffisant.
    # C'est sur en concurrence (deux acheteurs sur le dernier article) sans verrou explicite,
    # et fonctionne aussi bien sur SQLite que Postgres.
    try:
        for line in pricing["lines"]:
            res = db.execute(
                update(models.Product)
                .where(models.Product.id == line.product_id, models.Product.stock >= line.qty)
                .values(stock=models.Product.stock - line.qty)
            )
            if res.rowcount == 0:
                db.rollback()
                raise HTTPException(status.HTTP_409_CONFLICT, f"Stock insuffisant pour {line.name}.")

        # En prod : on capture le paiement ICI (Stripe) avant de confirmer.
        # Si la capture echoue, on rollback et le stock est rendu automatiquement.

        order = models.Order(
            number="ATL" + str(secrets.randbelow(900000) + 100000),
            user_id=user.id if user else None,
            email=str(data.email),
            status="paid",
            subtotal_cents=pricing["subtotal_cents"],
            discount_cents=pricing["discount_cents"],
            shipping_cents=pricing["shipping_cents"],
            total_cents=pricing["total_cents"],
            promo_code=pricing["promo"].code if pricing["promo"] else None,
        )
        db.add(order)
        db.flush()  # recupere order.id

        for line in pricing["lines"]:
            p = db.get(models.Product, line.product_id)
            db.add(models.OrderItem(
                order_id=order.id, product_id=p.id, name=p.name, art=p.art,
                unit_price_cents=line.unit_price_cents,
                # Fige le cout d'achat du moment, comme le prix paye.
                unit_cost_cents=p.cost_cents,
                qty=line.qty,
            ))

        db.commit()
        db.refresh(order)
        return order
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Echec du traitement de la commande.")


@router.get("", response_model=list[schemas.OrderOut])
def my_orders(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return orders


@router.get("/{number}", response_model=schemas.OrderOut)
def get_order(number: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).filter(models.Order.number == number).first()
    if order is None or order.user_id != user.id:
        raise HTTPException(404, "Commande introuvable.")
    return order
