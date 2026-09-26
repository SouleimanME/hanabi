from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .. import models, plongement, recherche, schemas
from ..config import settings
from ..antibot import verify as verify_antibot
from ..database import get_db
from ..deps import get_optional_user
from ..ratelimit import limiter
from ..translations import localize

router = APIRouter(prefix="/products", tags=["products"])


def _ratings_map(db: Session, product_ids: list[int]) -> dict[int, tuple[float, int]]:
    if not product_ids:
        return {}
    rows = db.execute(
        select(models.Review.product_id, func.avg(models.Review.rating), func.count(models.Review.id))
        .where(models.Review.product_id.in_(product_ids), models.Review.approved.is_(True))
        .group_by(models.Review.product_id)
    ).all()
    return {pid: (float(avg or 0), int(cnt)) for pid, avg, cnt in rows}


def _to_out(p: models.Product, rating: tuple[float, int], lang: str | None) -> schemas.ProductOut:
    out = schemas.ProductOut.model_validate(p)
    out.name, out.blurb = localize(p.code, lang, p.name, p.blurb)
    if not out.images:
        out.images = [p.art]
    out.rating_avg = round(rating[0], 2)
    out.rating_count = rating[1]
    return out


@router.get("", response_model=list[schemas.ProductOut])
def list_products(
    db: Session = Depends(get_db),
    category: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=80),
    sort: str = Query("pop", pattern="^(pertinence|pop|new|asc|desc)$"),
    lang: str | None = Query(None, max_length=5),
):
    products = db.scalars(select(models.Product).where(models.Product.active.is_(True))).all()

    # La recherche voit tout le catalogue, dans les trois langues, avant le
    # filtre de catégorie : le sens se juge par rapport à l'ensemble des objets
    rang: dict[int, int] | None = None
    if q and q.strip():
        encodeur = plongement.encodeur() if settings.RECHERCHE_SEMANTIQUE else None
        ordre = recherche.chercher([recherche.fiche(p) for p in products], q.strip(), encodeur)
        rang = {pid: i for i, pid in enumerate(ordre)}
        products = [p for p in products if p.id in rang]
    if category and category != "Tout":
        products = [p for p in products if p.category == category]

    ratings = _ratings_map(db, [p.id for p in products])
    out = [_to_out(p, ratings.get(p.id, (0.0, 0)), lang) for p in products]

    if sort == "pertinence" and rang is not None:
        out.sort(key=lambda x: rang[x.id])
    elif sort == "asc":
        out.sort(key=lambda x: x.price_cents)
    elif sort == "desc":
        out.sort(key=lambda x: -x.price_cents)
    elif sort == "new":
        out.sort(key=lambda x: (not x.is_new, -x.id))
    else:
        out.sort(key=lambda x: (-x.rating_count, -x.rating_avg))
    return out


@router.get("/featured", response_model=list[schemas.ProductOut])
def featured_products(db: Session = Depends(get_db), lang: str | None = Query(None)):
    """Produits mis en avant (pièce du mois), triés par `featured_order`."""
    stmt = (
        select(models.Product)
        .where(models.Product.active.is_(True), models.Product.featured.is_(True))
        .order_by(models.Product.featured_order, models.Product.id)
    )
    products = db.scalars(stmt).all()
    ratings = _ratings_map(db, [p.id for p in products])
    return [_to_out(p, ratings.get(p.id, (0.0, 0)), lang) for p in products]


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), lang: str | None = Query(None)):
    p = db.get(models.Product, product_id)
    if p is None or not p.active:
        raise HTTPException(404, "Produit introuvable.")
    ratings = _ratings_map(db, [p.id])
    return _to_out(p, ratings.get(p.id, (0.0, 0)), lang)


@router.post("/{product_id}/view", status_code=204)
@limiter.limit("60/minute")
def record_view(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    """Enregistre l'ouverture d'une fiche (audience et conversion du back-office).

    Silencieuse : un produit inconnu ne lève rien. Plafonnée par IP pour ne pas
    gonfler les compteurs.
    """
    if db.get(models.Product, product_id) is None:
        return

    db.add(models.ProductView(product_id=product_id, user_id=user.id if user else None))
    db.commit()


@router.post("/{product_id}/notify", status_code=201)
@limiter.limit("5/minute")
def notify_restock(
    request: Request, product_id: int, data: schemas.NotifyIn, db: Session = Depends(get_db)
):
    """Alerte de retour en stock. Formulaire public : barrière anti-robots."""
    verify_antibot(data.antibot, "notify")

    p = db.get(models.Product, product_id)
    if p is None or not p.active:
        raise HTTPException(404, "Produit introuvable.")
    existing = db.query(models.StockAlert).filter(
        models.StockAlert.product_id == product_id,
        func.lower(models.StockAlert.email) == data.email,
    ).first()
    if existing is None:
        db.add(models.StockAlert(product_id=product_id, email=data.email, lang=data.lang))
    elif existing.notified:
        # Déjà prévenu d'un précédent retour : la demande repart
        existing.notified = False
        existing.lang = data.lang
    db.commit()
    return {"ok": True}

@router.get("/{product_id}/affinites", response_model=list[schemas.ProductOut])
def affinites(
    product_id: int,
    db: Session = Depends(get_db),
    lang: str | None = Query(None, max_length=5),
    limit: int = Query(3, ge=1, le=6),
):
    """Produits achetés avec celui-ci, lus dans `gold.gold_affinites_produits`.

    Tri par lift, paires au-dessus de 1 seulement. Sans entrepôt, liste vide :
    la fiche reste consultable.
    """
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return []

    try:
        lignes = db.execute(
            text(
                # Paire stockée une fois (a < b) : chercher des deux côtés, rendre l'autre
                """
                select case when produit_a_id = :pid then produit_b_id else produit_a_id end as autre
                from gold.gold_affinites_produits
                where (produit_a_id = :pid or produit_b_id = :pid) and lift > 1
                order by lift desc
                limit :limite
                """
            ),
            {"pid": product_id, "limite": limit},
        ).all()
    except SQLAlchemyError:
        # Schéma absent ou droits manquants : comme sans entrepôt
        db.rollback()
        return []

    ids = [int(ligne[0]) for ligne in lignes]
    if not ids:
        return []

    produits = {
        p.id: p
        for p in db.scalars(
            select(models.Product).where(models.Product.id.in_(ids), models.Product.active.is_(True))
        )
    }
    notes = _ratings_map(db, list(produits))
    # Conserve l'ordre du lift
    return [
        _to_out(produits[pid], notes.get(pid, (0.0, 0)), lang) for pid in ids if pid in produits
    ]
