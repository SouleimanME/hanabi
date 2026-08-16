"""Tarification cote serveur.

Regle de securite : le total qui fait foi est calcule ici, a partir des prix
en base. Le front peut envoyer ce qu'il veut, on ne lui fait jamais confiance
sur les montants ni sur la validite d'un code promo.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from . import models, schemas

FREE_SHIPPING_THRESHOLD_CENTS = 8000  # 80 euros
SHIPPING_CENTS = 690                   # 6,90 euros


def _promo_label(p: models.Promo) -> str:
    if p.kind == "percent":
        return f"-{p.percent} %"
    if p.kind == "fixed":
        return f"-{p.amount_cents / 100:.2f} euros".replace(".", ",")
    return "Port offert"


# Le meme piege s'est represente sur la file d'attente des courriels, ou une
# comparaison de dates echouait pour cette raison exacte. L'aide vit desormais
# aupres des modeles, la ou sont declarees les colonnes concernees : c'est le
# seul endroit ou l'on pense a elle en ajoutant une date.
_as_utc = models.as_utc


def validate_promo(db: Session, code: str, subtotal_cents: int) -> models.Promo:
    promo = db.query(models.Promo).filter(models.Promo.code == code.strip().upper()).first()
    if promo is None or not promo.active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Code promo invalide.")
    if promo.expires_at and _as_utc(promo.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce code promo a expire.")
    if subtotal_cents < promo.min_subtotal_cents:
        seuil = promo.min_subtotal_cents / 100
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Minimum de {seuil:.2f} euros requis.")
    return promo


def quote(db: Session, items: list[schemas.CartLineIn], promo_code: str | None) -> dict:
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Panier vide.")

    lines: list[schemas.QuoteLineOut] = []
    subtotal = 0
    for it in items:
        p = db.get(models.Product, it.product_id)
        if p is None or not p.active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Produit {it.product_id} introuvable.")
        line_total = p.price_cents * it.qty
        subtotal += line_total
        lines.append(schemas.QuoteLineOut(
            product_id=p.id, name=p.name, unit_price_cents=p.price_cents,
            qty=it.qty, line_total_cents=line_total,
        ))

    discount = 0
    free_ship = False
    promo_out = None
    if promo_code:
        promo = validate_promo(db, promo_code, subtotal)
        if promo.kind == "percent":
            discount = subtotal * promo.percent // 100
        elif promo.kind == "fixed":
            discount = min(promo.amount_cents or 0, subtotal)
        elif promo.kind == "free_shipping":
            free_ship = True
        promo_out = schemas.PromoOut(code=promo.code, kind=promo.kind, label=_promo_label(promo))

    after = subtotal - discount
    shipping = 0 if (subtotal == 0 or after >= FREE_SHIPPING_THRESHOLD_CENTS or free_ship) else SHIPPING_CENTS
    total = after + shipping

    return {
        "lines": lines,
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "shipping_cents": shipping,
        "total_cents": total,
        "promo": promo_out,
    }
