import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from .. import emails, idempotency, models, outbox, payments, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_optional_user
from ..pricing import quote
from ..ratelimit import limiter

log = logging.getLogger("hanabi.commandes")

router = APIRouter(prefix="/orders", tags=["orders"])

# Tirages avant d'abandonner ; le jeu de démonstration occupe déjà environ 7 %
# des 900 000 numéros, sans quoi une commande sur quinze échouait.
TIRAGES_NUMERO = 20


def _numero_libre(db: Session) -> str:
    """Numéro de commande absent de la base (lecture sur l'index unique)."""
    for _ in range(TIRAGES_NUMERO):
        numero = payments.nouvelle_reference_commande()
        if db.scalar(select(models.Order.id).where(models.Order.number == numero)) is None:
            return numero
    raise RuntimeError("aucun numéro de commande libre")


# Route publique : plafond propre en plus de la limite globale
@router.post("/quote", response_model=schemas.QuoteOut)
@limiter.limit("60/minute")
def get_quote(request: Request, data: schemas.QuoteIn, db: Session = Depends(get_db)):
    """Recalcule le panier côté serveur (sous-total, remise, port, total)."""
    return quote(db, data.items, data.promo_code)


# Écrit stock, commande et courriel ; laisse la place aux réessais légitimes
@router.post("/checkout", response_model=schemas.OrderOut, status_code=201)
@limiter.limit("20/minute")
def checkout(
    request: Request,
    data: schemas.CheckoutIn,
    reponse: Response,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
    idempotency_key: str | None = Header(default=None, alias=idempotency.EN_TETE),
):
    """Crée la commande : stock, paiement, courriel, tout ou rien.

    Le stock est pris avant le paiement ; un refus le rend par rollback. Le
    courriel entre en file dans la même transaction. Avec `Idempotency-Key`, un
    réessai rend la réponse du premier appel.
    """
    # Carte enregistrée : filtrée sur le demandeur dans la requête
    jeton_paiement = data.payment_token
    if data.payment_method_id is not None:
        if user is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Il faut être connecté pour utiliser une carte enregistrée.",
            )
        moyen = db.scalar(
            select(models.PaymentMethod).where(
                models.PaymentMethod.id == data.payment_method_id,
                models.PaymentMethod.user_id == user.id,
            )
        )
        if moyen is None:
            # 404 plutôt que 403, qui confirmerait l'existence de la carte
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Moyen de paiement introuvable.")
        jeton_paiement = moyen.jeton

    # Refusé avant toute écriture ; vise la valeur `false` envoyée hors interface
    if not data.cgv_acceptees:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Les conditions générales de vente doivent être acceptées.",
        )

    cle = idempotency.valider(idempotency_key)
    trace = None
    if cle:
        try:
            trace = idempotency.reserver(
                db, cle, "orders.checkout", jsonable_encoder(data)
            )
        except idempotency.Rejeu as rejeu:
            return rejeu.reponse()

    pricing = quote(db, data.items, data.promo_code)

    try:
        # --- 1. Stock ---
        # `UPDATE ... WHERE stock >= qty` : rowcount 0 = stock insuffisant, sûr en
        # concurrence sur les deux moteurs. CHECK (stock >= 0) en dernier recours.
        for line in pricing["lines"]:
            res = db.execute(
                update(models.Product)
                .where(models.Product.id == line.product_id, models.Product.stock >= line.qty)
                .values(stock=models.Product.stock - line.qty)
            )
            if res.rowcount == 0:
                db.rollback()
                raise HTTPException(status.HTTP_409_CONFLICT, f"Stock insuffisant pour {line.name}.")

        livraison = data.shipping
        order = models.Order(
            number=_numero_libre(db),
            user_id=user.id if user else None,
            email=data.email,
            status="paid",
            subtotal_cents=pricing["subtotal_cents"],
            discount_cents=pricing["discount_cents"],
            shipping_cents=pricing["shipping_cents"],
            total_cents=pricing["total_cents"],
            promo_code=pricing["promo"].code if pricing["promo"] else None,
            ship_name=f"{livraison.prenom} {livraison.nom}",
            ship_addr=livraison.adresse,
            ship_cp=livraison.cp,
            ship_city=livraison.ville,
            cgv_version=settings.CGV_VERSION,
            cgv_acceptees_le=models.now_utc(),
        )
        db.add(order)
        db.flush()

        lignes = []
        for line in pricing["lines"]:
            p = db.get(models.Product, line.product_id)
            article = models.OrderItem(
                order_id=order.id, product_id=p.id, name=p.name, art=p.art,
                unit_price_cents=line.unit_price_cents,
                unit_cost_cents=p.cost_cents,
                qty=line.qty,
            )
            db.add(article)
            lignes.append(article)

        # --- 2. Paiement (simulé, voir payments.py) ---
        try:
            autorisation = payments.autoriser(
                jeton_paiement, pricing["total_cents"], order.number
            )
        except payments.PaiementRefuse as refus:
            # Rien n'est débité ; le rollback rend le stock
            db.rollback()
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, refus.motif) from refus
        except payments.PaiementIndecis:
            # Débit peut-être passé : ni confirmation ni annulation. La commande
            # reste en attente de rapprochement, stock retenu, et la ligne
            # d'idempotence est validée avec elle (un rollback l'emporterait et
            # rouvrirait la porte à un second débit).
            order.status = "pending"
            log.error(
                "paiement indecis : commande en attente de rapprochement",
                extra={"commande": order.number, "total_cents": order.total_cents},
            )
            if trace is not None:
                corps = json.dumps(jsonable_encoder(schemas.OrderOut.model_validate(order)))
                idempotency.conclure(db, trace, 202, corps)
            db.commit()
            db.refresh(order)
            # 202, sans courriel de confirmation
            reponse.status_code = status.HTTP_202_ACCEPTED
            return order

        order.payment_ref = autorisation.reference

        # --- 3. Courriel, inscrit en file dans la même transaction ---
        sujet, texte, html = emails.confirmation_commande(order, lignes)
        outbox.deposer(db, data.email, sujet, texte, html)

        if trace is not None:
            corps = json.dumps(jsonable_encoder(schemas.OrderOut.model_validate(order)))
            idempotency.conclure(db, trace, 201, corps)

        db.commit()
        db.refresh(order)
        log.info(
            "commande creee",
            extra={"numero": order.number, "total_cents": order.total_cents,
                   "paiement": autorisation.reference},
        )
        if cle:
            reponse.headers["Idempotent-Replay"] = "false"
        return order
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        log.exception("echec du traitement de la commande")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Échec du traitement de la commande.")


@router.get("", response_model=list[schemas.OrderOut])
def my_orders(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    # Articles chargés en une requête, pas une par commande
    return db.scalars(
        select(models.Order)
        .options(selectinload(models.Order.items))
        .where(models.Order.user_id == user.id)
        .order_by(models.Order.created_at.desc())
    ).all()


@router.get("/{number}", response_model=schemas.OrderOut)
def get_order(number: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).filter(models.Order.number == number).first()
    if order is None or order.user_id != user.id:
        raise HTTPException(404, "Commande introuvable.")
    return order
