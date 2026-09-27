"""Tarification côté serveur : le total qui fait foi se calcule ici, depuis les prix en base.

Frais de port dupliqués dans hanabi-front/src/lib/constants.js (un test compare).
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas, variantes

FREE_SHIPPING_THRESHOLD_CENTS = 8000  # 80 euros
SHIPPING_CENTS = 690                   # 6,90 euros


def _promo_label(p: models.Promo) -> str:
    if p.kind == "percent":
        return f"-{p.percent} %"
    if p.kind == "fixed":
        return f"-{p.amount_cents / 100:.2f} €".replace(".", ",")
    return "Port offert"


_as_utc = models.as_utc


def validate_promo(db: Session, code: str, subtotal_cents: int) -> models.Promo:
    promo = db.query(models.Promo).filter(models.Promo.code == code.strip().upper()).first()
    if promo is None or not promo.active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Code promo invalide.")
    if promo.expires_at and _as_utc(promo.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ce code promo a expiré.")
    if subtotal_cents < promo.min_subtotal_cents:
        seuil = f"{promo.min_subtotal_cents / 100:.2f}".replace(".", ",")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Minimum de {seuil} € requis.")
    return promo


def choisir_variante(p: models.Product, variante_id: int | None) -> models.Variante | None:
    """La déclinaison demandée, vérifiée ; None pour un objet simple.

    Le prix vient toujours d'ici, jamais du panier : une déclinaison d'un
    autre objet ou retirée de la vente est refusée.
    """
    en_vente = variantes.actives(p)
    if not en_vente:
        if variante_id is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{p.name} ne se décline pas.")
        return None
    if variante_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Choisis une déclinaison de {p.name}.")
    variante = next((v for v in en_vente if v.id == variante_id), None)
    if variante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Cette déclinaison de {p.name} n'est plus en vente.")
    return variante


def quote(db: Session, items: list[schemas.CartLineIn], promo_code: str | None) -> dict:
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Panier vide.")

    # Une seule lecture pour tout le panier, quel que soit le nombre de lignes
    demandes = {it.product_id for it in items}
    catalogue = {
        p.id: p
        for p in db.scalars(
            select(models.Product).where(models.Product.id.in_(demandes))
        )
    }

    lines: list[schemas.QuoteLineOut] = []
    subtotal = 0
    for it in items:
        p = catalogue.get(it.product_id)
        if p is None or not p.active:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Produit {it.product_id} introuvable.")
        variante = choisir_variante(p, it.variante_id)
        prix = variante.price_cents if variante else p.price_cents
        line_total = prix * it.qty
        subtotal += line_total
        lines.append(schemas.QuoteLineOut(
            product_id=p.id, name=p.name, unit_price_cents=prix,
            variante_id=variante.id if variante else None,
            variante_libelle=variante.libelle if variante else None,
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
