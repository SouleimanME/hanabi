"""Back-office : tableau de bord, analytique, catalogue, promos, commandes, clients.

Lecture pour tout administrateur (`get_admin_user`), écriture refusée au compte
de démonstration (`get_admin_writer`).
"""
import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import exists, func, literal_column, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import analytics, models, restock
from ..analytics import REVENUE_STATUSES
from ..database import get_db
from ..deps import get_admin_user, get_admin_writer, is_readonly_admin
from ..pii import (
    masquer_date_naissance, masquer_email, masquer_nom, masquer_personne, masquer_ville,
)
from ..ratelimit import limiter

router = APIRouter(prefix="/admin", tags=["admin"])

# Visuel principal : blason court ou photo en base64 (carré de 1200 px, environ
# 700 000 caractères)
ART_MAX_LENGTH = 1_500_000

# Familles du catalogue, filtrées par la boutique (hanabi-front/src/lib/constants.js).
# Une autre valeur rendrait l'objet introuvable par le filtre.
CATEGORIES = ("Compagnons", "Tradition", "Collection")
MOTIF_CATEGORIE = "^(" + "|".join(CATEGORIES) + ")$"

# Vues de la galerie d'un produit
IMAGES_MAX = 8

# Statut suivant autorisé ; le même tableau guide les boutons du back-office
# (hanabi-front/src/admin/format.js). Annulée et remboursée sont définitives.
TRANSITIONS = {
    "pending": {"paid", "cancelled"},
    "paid": {"shipped", "cancelled"},
    "shipped": {"delivered", "refunded"},
    "delivered": set(),
    "cancelled": set(),
    "refunded": set(),
}

# L'annulation d'une commande pas encore expédiée remet ses articles en rayon
REMISE_EN_STOCK = {("pending", "cancelled"), ("paid", "cancelled")}

LIBELLES_STATUT = {
    "pending": "en attente", "paid": "payée", "shipped": "expédiée",
    "delivered": "livrée", "cancelled": "annulée", "refunded": "remboursée",
}


def _masquer_si(bride: bool, ligne: dict | None) -> dict | None:
    return masquer_personne(ligne) if bride else ligne


# --- Schémas ---
class ProductIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9-]{1,19}$")
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(pattern=MOTIF_CATEGORIE)
    blurb: str = Field(max_length=255)
    price_cents: int = Field(ge=0)
    stock: int = Field(ge=0)
    is_new: bool = False
    active: bool = True
    featured: bool = False
    featured_order: int = 0
    art: str = Field(default="torii,#E0452A,#0A0605", max_length=ART_MAX_LENGTH)
    images: list[str] = Field(default=[], max_length=IMAGES_MAX)


class ProductPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=160)
    category: str | None = Field(None, pattern=MOTIF_CATEGORIE)
    blurb: str | None = Field(None, max_length=255)
    price_cents: int | None = Field(None, ge=0)
    stock: int | None = Field(None, ge=0)
    is_new: bool | None = None
    active: bool | None = None
    featured: bool | None = None
    featured_order: int | None = None
    art: str | None = Field(None, max_length=ART_MAX_LENGTH)
    images: list[str] | None = Field(None, max_length=IMAGES_MAX)


class PromoIn(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    kind: str = Field(pattern="^(percent|fixed|free_shipping)$")
    percent: int | None = Field(None, ge=1, le=100)
    amount_cents: int | None = Field(None, ge=1)
    min_subtotal_cents: int = Field(0, ge=0)
    active: bool = True
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _montant_selon_le_type(self):
        """Un pourcentage sans taux ou une remise sans montant faisait échouer le devis."""
        if self.kind == "percent" and self.percent is None:
            raise ValueError("Un code en pourcentage demande un taux.")
        if self.kind == "fixed" and self.amount_cents is None:
            raise ValueError("Un code à montant fixe demande un montant.")
        # Le champ du type non retenu est vidé plutôt qu'ignoré en silence
        if self.kind != "percent":
            self.percent = None
        if self.kind != "fixed":
            self.amount_cents = None
        self.code = self.code.strip().upper()
        return self


class AdminUserOut(BaseModel):
    id: int
    name: str
    email: str
    civility: str | None
    birthdate: str | None
    city: str | None
    is_admin: bool
    created_at: datetime
    order_count: int = 0
    total_spent_cents: int = 0


# --- Tableau de bord ---
@router.get("/whoami")
def whoami(admin=Depends(get_admin_user)):
    """Compte connecté ; `readonly` sert à griser l'interface, le refus reste serveur."""
    return {
        "name": admin.name,
        "email": admin.email,
        "readonly": is_readonly_admin(admin),
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    from datetime import date as date_cls
    bride = is_readonly_admin(admin)
    revenue = db.execute(
        select(func.sum(models.Order.total_cents)).where(
            models.Order.status.in_(REVENUE_STATUSES)
        )
    ).scalar() or 0
    order_count = db.execute(
        select(func.count(models.Order.id)).where(models.Order.status.in_(REVENUE_STATUSES))
    ).scalar() or 0
    product_count = db.query(models.Product).filter(models.Product.active.is_(True)).count()
    low_stock = db.query(models.Product).filter(
        models.Product.active.is_(True), models.Product.stock <= 4
    ).count()
    pending_alerts = db.query(models.StockAlert).filter(
        models.StockAlert.notified.is_(False)
    ).count()
    recent_orders = db.query(models.Order).order_by(
        models.Order.created_at.desc()
    ).limit(5).all()

    # --- Démographie, agrégée par la base ---
    user_count = db.execute(select(func.count(models.User.id))).scalar() or 0

    civility_counts = {"M": 0, "F": 0, "N": 0, "?": 0}
    for value, n in db.execute(
        select(models.User.civility, func.count(models.User.id)).group_by(models.User.civility)
    ).all():
        civility_counts[value if value in civility_counts else "?"] += n

    # Tranches d'âge d'après l'année de naissance (à un an près)
    today = date_cls.today()
    age_buckets = {"<18": 0, "18-24": 0, "25-34": 0, "35-44": 0, "45-54": 0, "55+": 0, "?": 0}
    # Une seule expression pour SELECT et GROUP BY : PostgreSQL les veut identiques
    annee_naissance = func.substr(models.User.birthdate, literal_column("1"), literal_column("4"))
    for year, n in db.execute(
        select(annee_naissance, func.count(models.User.id)).group_by(annee_naissance)
    ).all():
        try:
            age = today.year - int(year)
        except (TypeError, ValueError):
            age_buckets["?"] += n
            continue
        if age < 18:   age_buckets["<18"] += n
        elif age < 25: age_buckets["18-24"] += n
        elif age < 35: age_buckets["25-34"] += n
        elif age < 45: age_buckets["35-44"] += n
        elif age < 55: age_buckets["45-54"] += n
        else:          age_buckets["55+"] += n

    top_cities = db.execute(
        select(models.User.city, func.count(models.User.id).label("n"))
        .where(models.User.city.isnot(None), models.User.city != "")
        .group_by(models.User.city)
        .order_by(func.count(models.User.id).desc())
        .limit(8)
    ).all()

    return {
        "revenue_cents": revenue,
        "order_count": order_count,
        "user_count": user_count,
        "product_count": product_count,
        "low_stock_count": low_stock,
        "pending_alerts": pending_alerts,
        "recent_orders": [
            _masquer_si(bride, {
                "number": o.number, "email": o.email, "total_cents": o.total_cents,
                "created_at": o.created_at.isoformat(), "status": o.status,
            })
            for o in recent_orders
        ],
        "demographics": {
            "civility": civility_counts,
            "age_buckets": age_buckets,
            "top_cities": [{"city": c, "count": n} for c, n in top_cities],
        },
    }


# --- Analytique ---
# Une route par vue : les plus coûteuses ne se calculent qu'à l'ouverture.
# Les calculs vivent dans app/analytics.py.


@router.get("/analytics")
def analytics_overview(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
    months: int = Query(12, ge=3, le=36),
    days: int = Query(30, ge=7, le=365, description="Fenêtre de comparaison, en jours"),
):
    """Vue d'ensemble : période courante, période précédente, catalogue."""
    bride = is_readonly_admin(admin)
    produits = analytics.catalogue(db)
    return {
        "months": months,
        "period": analytics.period_overview(db, days),
        "kpis": analytics.lifetime_kpis(db),
        "series": analytics.monthly_series(db, months),
        "products": produits,
        "categories": analytics.categories(db, produits),
        "profitability": analytics.profitability(produits),
        "correlation": analytics.audience_correlation(produits),
        "promos": analytics.promo_performance(db),
        "statuses": analytics.status_breakdown(db),
        "top_customers": [_masquer_si(bride, c) for c in analytics.top_customers(db)],
    }


@router.get("/analytics/audience")
def analytics_audience(
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
    city: str | None = Query(None, max_length=120),
    age: str | None = Query(None, max_length=10),
    civility: str | None = Query(None, max_length=2),
):
    """Portrait d'achat d'un segment ; sans filtre, toute la clientèle (référence)."""
    portrait = analytics.audience_profile(db, city=city, age=age, civility=civility)
    if is_readonly_admin(admin):
        portrait["best_customer"] = masquer_personne(portrait["best_customer"])
        portrait["biggest_order"] = masquer_personne(portrait["biggest_order"])
    return portrait


@router.get("/analytics/forecast")
def analytics_forecast(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    months: int = Query(12, ge=6, le=36),
    horizon: int = Query(3, ge=1, le=6),
):
    """Tendance du chiffre d'affaires et projection à court terme."""
    return analytics.forecast(db, months, horizon)


@router.get("/analytics/cohorts")
def analytics_cohorts(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    months: int = Query(12, ge=3, le=24),
):
    """Rétention par cohorte d'inscription."""
    return analytics.cohorts(db, months)


@router.get("/analytics/segments")
def analytics_segments(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    """Segmentation RFM des acheteurs."""
    segmentation = analytics.rfm_segments(db)
    if is_readonly_admin(admin):
        segmentation["examples"] = [masquer_personne(e) for e in segmentation["examples"]]
    return segmentation


@router.get("/analytics/affinities")
def analytics_affinities(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    limit: int = Query(12, ge=3, le=50),
):
    """Produits achetés ensemble, classés par lift."""
    return analytics.affinities(db, limit)


# --- Produits ---
@router.get("/products")
def list_products(
    db: Session = Depends(get_db), _=Depends(get_admin_user),
    include_inactive: bool = Query(False),
):
    q = db.query(models.Product)
    if not include_inactive:
        q = q.filter(models.Product.active.is_(True))
    products = q.order_by(models.Product.id).all()
    return [_prod_dict(p) for p in products]


@router.post("/products", status_code=201)
def create_product(data: ProductIn, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    if db.query(models.Product).filter(models.Product.code == data.code).first():
        raise HTTPException(409, f"Code produit '{data.code}' déjà utilisé.")
    p = models.Product(
        code=data.code, name=data.name, category=data.category, blurb=data.blurb,
        price_cents=data.price_cents, stock=data.stock, is_new=data.is_new,
        active=data.active, featured=data.featured, featured_order=data.featured_order,
        art=data.art, images=json.dumps(data.images),
    )
    db.add(p); db.commit(); db.refresh(p)
    return _prod_dict(p)


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db), _=Depends(get_admin_user)):
    p = db.get(models.Product, product_id)
    if not p:
        raise HTTPException(404, "Produit introuvable.")
    return _prod_dict(p)


@router.patch("/products/{product_id}")
def update_product(product_id: int, data: ProductPatch, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    p = db.get(models.Product, product_id)
    if not p:
        raise HTTPException(404, "Produit introuvable.")
    etait_indisponible = p.stock <= 0 or not p.active
    for field, val in data.model_dump(exclude_none=True).items():
        if field == "images":
            setattr(p, "images", json.dumps(val))
        else:
            setattr(p, field, val)

    # Réassort d'un objet épuisé : les alertes demandées sur la fiche partent
    prevenus = restock.signaler_retour(db, p) if etait_indisponible else 0

    db.commit(); db.refresh(p)
    return {**_prod_dict(p), "alertes_envoyees": prevenus}


# Tables qui désignent un produit : le supprimer casserait leurs clés
_REFERENCES_PRODUIT = (
    models.OrderItem.product_id,
    models.ProductView.product_id,
    models.Review.product_id,
    models.StockAlert.product_id,
)


@router.delete("/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    """Supprime un produit jamais vu ni commandé ; sinon le retire de la vente.

    Rend l'action réellement faite, pour que l'interface le dise.
    """
    p = db.get(models.Product, product_id)
    if not p:
        raise HTTPException(404, "Produit introuvable.")
    reference = db.scalar(
        select(or_(*(exists().where(colonne == product_id) for colonne in _REFERENCES_PRODUIT)))
    )
    if reference:
        p.active = False
        action = "desactive"
    else:
        db.delete(p)
        action = "supprime"
    db.commit()
    return {"action": action}


def _prod_dict(p: models.Product) -> dict:
    imgs = []
    try:
        imgs = json.loads(p.images) if p.images else []
    except Exception:
        pass
    return {
        "id": p.id, "code": p.code, "name": p.name, "category": p.category,
        "blurb": p.blurb, "price_cents": p.price_cents, "stock": p.stock,
        "is_new": p.is_new, "active": p.active,
        "featured": p.featured, "featured_order": p.featured_order,
        "art": p.art, "images": imgs,
    }


# --- Codes promo ---
@router.get("/promos")
def list_promos(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    return db.query(models.Promo).order_by(models.Promo.id).all()


def _code_pris(db: Session, code: str, sauf: int | None = None) -> bool:
    requete = select(models.Promo.id).where(models.Promo.code == code)
    if sauf is not None:
        requete = requete.where(models.Promo.id != sauf)
    return db.scalar(requete) is not None


@router.post("/promos", status_code=201)
def create_promo(data: PromoIn, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    # `data.code` arrive en majuscules, sans espaces autour (voir PromoIn)
    if _code_pris(db, data.code):
        raise HTTPException(409, "Ce code existe déjà.")
    promo = models.Promo(**data.model_dump())
    db.add(promo); db.commit(); db.refresh(promo)
    return promo


@router.patch("/promos/{promo_id}")
def update_promo(promo_id: int, data: PromoIn, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    """Remplace la définition du code. Le formulaire envoie tous les champs."""
    promo = db.get(models.Promo, promo_id)
    if not promo:
        raise HTTPException(404, "Code promo introuvable.")
    if _code_pris(db, data.code, sauf=promo_id):
        raise HTTPException(409, "Ce code existe déjà.")
    # Tous les champs, nuls compris : passer d'un pourcentage à un montant fixe
    # ne doit pas laisser l'ancien taux derrière
    for field, val in data.model_dump().items():
        setattr(promo, field, val)
    db.commit(); db.refresh(promo)
    return promo


@router.delete("/promos/{promo_id}", status_code=204)
def delete_promo(promo_id: int, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    promo = db.get(models.Promo, promo_id)
    if not promo:
        raise HTTPException(404, "Code promo introuvable.")
    db.delete(promo); db.commit()


# --- Commandes ---
@router.get("/orders")
def list_orders(
    db: Session = Depends(get_db), admin=Depends(get_admin_user),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=120, description="Numéro ou e-mail, en partie"),
    statut: str | None = Query(None, pattern="^(pending|paid|shipped|delivered|cancelled|refunded)$"),
):
    """Commandes récentes. La recherche porte sur toute la base, pas sur la page chargée."""
    bride = is_readonly_admin(admin)
    requete = select(models.Order)
    if q and q.strip():
        motif = f"%{q.strip().lower()}%"
        requete = requete.where(
            or_(func.lower(models.Order.number).like(motif), func.lower(models.Order.email).like(motif))
        )
    if statut:
        requete = requete.where(models.Order.status == statut)

    total = db.scalar(select(func.count()).select_from(requete.subquery())) or 0
    commandes = db.scalars(
        requete.options(selectinload(models.Order.items))
        .order_by(models.Order.created_at.desc(), models.Order.id.desc())
        .offset(offset).limit(limit)
    ).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "masque": bride,
        "items": [
            _masquer_si(bride, {
                "number": o.number, "email": o.email, "status": o.status,
                "total_cents": o.total_cents, "created_at": o.created_at.isoformat(),
                "ship_name": o.ship_name, "ship_addr": o.ship_addr,
                "ship_cp": o.ship_cp, "ship_city": o.ship_city,
                "next": sorted(TRANSITIONS.get(o.status, ())),
                "items": [
                    {"name": i.name, "qty": i.qty, "unit_price_cents": i.unit_price_cents}
                    for i in o.items
                ],
            })
            for o in commandes
        ],
    }


# Export plafonné pour le compte de démonstration, même avec e-mails masqués
EXPORT_MAX_DEMO = 100

# Premiers caractères qu'un tableur interprète comme une formule
_AMORCES_FORMULE = ("=", "+", "-", "@", "\t", "\r", "\n")


def _cellule_csv(valeur: str) -> str:
    """Neutralise une cellule qu'un tableur exécuterait comme formule (CWE-1236).

    La partie locale d'un e-mail accepte `=`, `+` et `-` (`=1+1@exemple.fr`) et
    vient d'une saisie publique. Une apostrophe en tête force le texte.
    """
    if valeur and valeur.startswith(_AMORCES_FORMULE):
        return "'" + valeur
    return valeur

# Route la plus coûteuse du back-office : plafonnée pour ne pas épuiser le pool
@router.get("/orders.csv")
@limiter.limit("10/minute")
def export_orders_csv(
    request: Request,
    db: Session = Depends(get_db), admin=Depends(get_admin_user),
    status_val: str | None = Query(None, alias="status"),
):
    """Commandes en CSV, une ligne par article.

    Montants en euros à virgule et BOM UTF-8, pour Excel en configuration française.
    """
    bride = is_readonly_admin(admin)

    # Articles chargés par lots : une requête par commande épuisait le pool
    query = (
        db.query(models.Order)
        .options(selectinload(models.Order.items))
        .order_by(models.Order.created_at.desc())
    )
    if status_val:
        query = query.filter(models.Order.status == status_val)
    if bride:
        query = query.limit(EXPORT_MAX_DEMO)

    buffer = io.StringIO()
    # QUOTE_ALL : un point-virgule dans une valeur ne décale pas les colonnes
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow([
        "numero", "date", "statut", "email",
        "produit", "quantite", "prix_unitaire_eur", "total_ligne_eur",
        "total_commande_eur", "remise_eur", "port_eur", "code_promo",
    ])

    def eur(cents: int) -> str:
        return f"{cents / 100:.2f}".replace(".", ",")

    for order in query.all():
        for item in order.items:
            writer.writerow([
                _cellule_csv(order.number),
                order.created_at.isoformat(timespec="seconds"),
                _cellule_csv(order.status),
                _cellule_csv(masquer_email(order.email) if bride else order.email),
                _cellule_csv(item.name),
                item.qty,
                eur(item.unit_price_cents),
                eur(item.unit_price_cents * item.qty),
                eur(order.total_cents),
                eur(order.discount_cents),
                eur(order.shipping_cents),
                _cellule_csv(order.promo_code or ""),
            ])

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="hanabi-commandes-{stamp}.csv"'},
    )


@router.patch("/orders/{number}/status")
def update_order_status(
    number: str, status_val: str = Query(..., alias="status"),
    db: Session = Depends(get_db), _=Depends(get_admin_writer),
):
    """Fait avancer une commande d'un statut au suivant (voir TRANSITIONS).

    Une annulation avant expédition remet les articles en stock, et prévient
    les personnes qui attendaient un objet épuisé.
    """
    if status_val not in TRANSITIONS:
        raise HTTPException(422, f"Statut invalide. Valeurs : {', '.join(sorted(TRANSITIONS))}")
    order = db.scalar(
        select(models.Order)
        .options(selectinload(models.Order.items))
        .where(models.Order.number == number)
    )
    if not order:
        raise HTTPException(404, "Commande introuvable.")

    depart = order.status
    if status_val not in TRANSITIONS.get(depart, set()):
        suivants = sorted(TRANSITIONS.get(depart, set()))
        possibles = ", ".join(LIBELLES_STATUT[s] for s in suivants) or "aucun, ce statut est définitif"
        raise HTTPException(
            409,
            f"Une commande {LIBELLES_STATUT.get(depart, depart)} ne peut pas devenir "
            f"{LIBELLES_STATUT[status_val]}. Suivants possibles : {possibles}.",
        )

    remis = 0
    if (depart, status_val) in REMISE_EN_STOCK:
        for article in order.items:
            produit = db.get(models.Product, article.product_id)
            if produit is None:
                continue
            etait_epuise = produit.stock <= 0
            produit.stock += article.qty
            remis += article.qty
            if etait_epuise:
                restock.signaler_retour(db, produit)

    order.status = status_val
    db.commit()
    return {"number": order.number, "status": order.status, "remis_en_stock": remis}


# --- Clients ---
@router.get("/users")
def list_users(
    db: Session = Depends(get_db), admin=Depends(get_admin_user),
    q: str | None = Query(None, max_length=120, description="Filtre sur le nom, l'e-mail ou la ville"),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
):
    """Clients paginés, avec commandes et total dépensé en une jointure agrégée."""
    depenses = (
        select(
            models.Order.user_id.label("user_id"),
            func.count(models.Order.id).label("n"),
            func.coalesce(func.sum(models.Order.total_cents), 0).label("total"),
        )
        .where(models.Order.status.in_(REVENUE_STATUSES), models.Order.user_id.isnot(None))
        .group_by(models.Order.user_id)
        .subquery()
    )

    stmt = (
        select(
            models.User,
            func.coalesce(depenses.c.n, 0),
            func.coalesce(depenses.c.total, 0),
        )
        .outerjoin(depenses, depenses.c.user_id == models.User.id)
    )

    if q:
        motif = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            func.lower(models.User.name).like(motif)
            | func.lower(models.User.email).like(motif)
            | func.lower(func.coalesce(models.User.city, "")).like(motif)
        )

    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar() or 0

    lignes = db.execute(
        stmt.order_by(models.User.created_at.desc(), models.User.id.desc())
        .offset(offset).limit(limit)
    ).all()

    # Compte de démonstration : lignes masquées. La recherche porte sur les
    # vraies valeurs mais ne rend que du masqué.
    bride = is_readonly_admin(admin)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "masque": bride,
        "items": [
            AdminUserOut(
                id=u.id,
                name=masquer_nom(u.name) if bride else u.name,
                email=masquer_email(u.email) if bride else u.email,
                civility=u.civility,
                birthdate=masquer_date_naissance(u.birthdate) if bride else u.birthdate,
                city=masquer_ville(u.city) if bride else u.city,
                is_admin=u.is_admin,
                created_at=u.created_at,
                order_count=int(n), total_spent_cents=int(depense),
            )
            for u, n, depense in lignes
        ],
    }


@router.patch("/users/{user_id}/admin")
def toggle_admin(user_id: int, is_admin: bool = Query(...), db: Session = Depends(get_db), admin=Depends(get_admin_writer)):
    if admin.id == user_id:
        raise HTTPException(400, "Tu ne peux pas modifier ton propre rôle.")
    u = db.get(models.User, user_id)
    if not u:
        raise HTTPException(404, "Utilisateur introuvable.")
    u.is_admin = is_admin
    db.commit()
    return {"id": u.id, "is_admin": u.is_admin}


# --- Alertes de stock ---
@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    """Alertes de retour en stock en attente. Adresses saisies par des visiteurs : masquées pour la démonstration."""
    bride = is_readonly_admin(admin)
    lignes = db.execute(
        select(models.StockAlert, models.Product.name)
        .join(models.Product, models.Product.id == models.StockAlert.product_id)
        .where(models.StockAlert.notified.is_(False))
        .order_by(models.StockAlert.created_at.desc())
    ).all()
    return [
        _masquer_si(bride, {
            "id": a.id, "product_id": a.product_id, "product": nom,
            "email": a.email, "created_at": a.created_at.isoformat(),
        })
        for a, nom in lignes
    ]
