import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .. import models, schemas
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
    category: str | None = Query(None),
    q: str | None = Query(None),
    sort: str = Query("pop", pattern="^(pop|new|asc|desc)$"),
    lang: str | None = Query(None),
):
    stmt = select(models.Product).where(models.Product.active.is_(True))
    if category and category != "Tout":
        stmt = stmt.where(models.Product.category == category)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(models.Product.name).like(like) | func.lower(models.Product.category).like(like))
    products = db.scalars(stmt).all()
    ratings = _ratings_map(db, [p.id for p in products])

    out = [_to_out(p, ratings.get(p.id, (0.0, 0)), lang) for p in products]
    if sort == "asc":
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
    """Produits mis en avant dans le carrousel, triés par featured_order."""
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
    """Enregistre l'ouverture d'une fiche produit.

    Alimente les indicateurs d'audience du back-office : articles les plus et
    les moins consultes, et surtout taux de conversion, qui rapporte les
    commandes aux vues et n'a donc aucun sens sans cette mesure.

    Volontairement silencieuse. Un produit inconnu ne provoque pas d'erreur :
    c'est une mesure d'usage, pas une operation metier, et faire remonter un
    404 dans la console d'un visiteur pour une fiche supprimee entre-temps
    n'apporte rien. Meme raison pour le 204 sans corps — le client n'a rien a
    faire de la reponse.

    Le plafond de 60 appels par minute et par IP evite qu'un rafraichissement
    automatique gonfle les compteurs sans rien empecher d'une navigation
    normale, qui ouvre rarement plus d'une fiche par seconde.
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
    """Alerte retour en stock : enregistre une demande pour un produit epuise.

    Formulaire ouvert sans authentification : c'est la porte d'entree la plus
    exposee du site, et elle enregistre une adresse e-mail. Sans barriere, elle
    sert a inonder la base d'adresses arbitraires.
    """
    verify_antibot(data.antibot, "notify")

    p = db.get(models.Product, product_id)
    if p is None:
        raise HTTPException(404, "Produit introuvable.")
    existing = db.query(models.StockAlert).filter(
        models.StockAlert.product_id == product_id, models.StockAlert.email == str(data.email)
    ).first()
    if not existing:
        db.add(models.StockAlert(product_id=product_id, email=str(data.email)))
        db.commit()
    return {"ok": True}

@router.get("/{product_id}/affinites", response_model=list[schemas.ProductOut])
def affinites(
    product_id: int,
    db: Session = Depends(get_db),
    lang: str | None = Query(None, max_length=5),
    limit: int = Query(3, ge=1, le=6),
):
    """Produits reellement achetes avec celui-ci, par ordre de lift decroissant.

    C'est la seule route publique qui lit l'entrepot decisionnel. Les
    suggestions ne viennent donc pas d'une regle ecrite a la main - « meme
    categorie », « meme tranche de prix » - mais des paniers reels : la table
    `gold.gold_affinites_produits`, construite par dbt, mesure pour chaque
    paire a quel point elle depasse le hasard.

    Le tri se fait sur le LIFT et non sur la confiance. La confiance se laisse
    tromper par les articles populaires - tout se vend avec le best-seller - la
    ou le lift rapporte la frequence observee a celle qu'on attendrait si les
    deux achats etaient independants. Seules les paires au-dessus de 1 sont
    proposees : en dessous, les deux articles se substituent plutot qu'ils ne
    se completent, et les recommander ensemble serait un contresens.

    Degradation volontaire. Sans entrepot - base SQLite en developpement,
    schemas non construits, table vide - la reponse est une liste vide, jamais
    une erreur : la fiche produit doit rester consultable quoi qu'il arrive.
    L'appelant se contente alors de ne rien afficher.
    """
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return []

    try:
        lignes = db.execute(
            text(
                # La paire est stockee une seule fois, dans un ordre stable
                # (produit_a_id < produit_b_id) : il faut donc chercher des
                # deux cotes et rendre a chaque fois l'AUTRE article.
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
        # Schema absent ou droits manquants : meme reponse que sans entrepot.
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
    # L'ordre du lift est celui de la requete, pas celui de la table `products` :
    # on reconstruit la liste a partir des identifiants, sans quoi la meilleure
    # suggestion pourrait se retrouver en derniere position.
    return [
        _to_out(produits[pid], notes.get(pid, (0.0, 0)), lang) for pid in ids if pid in produits
    ]
