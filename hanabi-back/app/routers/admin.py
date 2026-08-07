"""
Router admin - accessible uniquement aux utilisateurs is_admin=True.
Fournit tout ce qu'il faut pour gérer le catalogue sans toucher au code.
"""
import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from .. import analytics, models
from ..analytics import REVENUE_STATUSES
from ..database import get_db
from ..deps import get_admin_user, get_admin_writer, is_readonly_admin
from ..security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])

# Longueur maximale du visuel principal, en caracteres.
#
# Il contient soit un motif court, soit une photo en data URI base64. Le
# back-office ramene la photo principale a un carre de 1200 px, ce qui donne
# environ 700 000 caracteres apres encodage ; 1,5 million laisse de la marge
# tout en gardant une borne.
ART_MAX_LENGTH = 1_500_000


# ------------------------------------------------------------------ #
# Schemas admin                                                        #
# ------------------------------------------------------------------ #
class ProductIn(BaseModel):
    code: str = Field(max_length=20)
    name: str = Field(max_length=160)
    category: str = Field(max_length=40)
    blurb: str = Field(max_length=255)
    price_cents: int = Field(ge=0)
    stock: int = Field(ge=0)
    is_new: bool = False
    active: bool = True
    featured: bool = False
    featured_order: int = 0
    # Le plafond de 60 caracteres ne valait que pour un motif « forme,c1,c2 ».
    # Or ce champ recoit aussi la photo principale, encodee en base64 : un carre
    # de 1200 px pese environ 700 000 caracteres une fois encode. On garde une
    # borne, pour qu'un seul champ ne puisse pas absorber tout le corps autorise.
    art: str = Field(default="circles,#224A3F,#E4D7BF", max_length=ART_MAX_LENGTH)
    images: list[str] = []


class ProductPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    blurb: str | None = None
    price_cents: int | None = Field(None, ge=0)
    stock: int | None = Field(None, ge=0)
    is_new: bool | None = None
    active: bool | None = None
    featured: bool | None = None
    featured_order: int | None = None
    # Meme borne qu'a la creation : sans elle, la modification etait un chemin
    # detourne pour deposer un champ de taille arbitraire.
    art: str | None = Field(None, max_length=ART_MAX_LENGTH)
    images: list[str] | None = None


class PromoIn(BaseModel):
    code: str = Field(max_length=40)
    kind: str = Field(pattern="^(percent|fixed|free_shipping)$")
    percent: int | None = Field(None, ge=1, le=100)
    amount_cents: int | None = Field(None, ge=0)
    min_subtotal_cents: int = 0
    active: bool = True
    expires_at: datetime | None = None


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


# ------------------------------------------------------------------ #
# Stats tableau de bord                                               #
# ------------------------------------------------------------------ #
@router.get("/whoami")
def whoami(admin=Depends(get_admin_user)):
    """Identite du compte connecte au back-office.

    Sert a l'interface pour signaler, et griser, ce que le compte vitrine ne
    peut pas faire. Ce n'est qu'un confort d'affichage : le refus qui compte
    est prononce par `get_admin_writer`, cote serveur.
    """
    return {
        "name": admin.name,
        "email": admin.email,
        "readonly": is_readonly_admin(admin),
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    from datetime import date as date_cls
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

    # --- Démographie clients ---
    #
    # Agrégée par la base, et non en Python. La version précédente chargeait
    # toute la table `users` en mémoire pour la parcourir trois fois : tenable
    # sur douze comptes de démonstration, ruineux dès que la clientèle se
    # compte en milliers. Trois `GROUP BY` renvoient ici quelques dizaines de
    # lignes au lieu de dix mille objets.
    user_count = db.execute(select(func.count(models.User.id))).scalar() or 0

    # Répartition par civilité (sexe)
    civility_counts = {"M": 0, "F": 0, "N": 0, "?": 0}
    for value, n in db.execute(
        select(models.User.civility, func.count(models.User.id)).group_by(models.User.civility)
    ).all():
        civility_counts[value if value in civility_counts else "?"] += n

    # Répartition par tranche d'âge.
    #
    # Regroupée sur l'année de naissance : l'âge en est déduit à un an près,
    # ce qui peut déplacer une poignée de personnes d'une tranche à l'autre.
    # L'écart est sans effet sur la forme de l'histogramme, seule chose que
    # cette vue cherche à montrer, et évite de rapatrier une date par client.
    today = date_cls.today()
    age_buckets = {"<18": 0, "18-24": 0, "25-34": 0, "35-44": 0, "45-54": 0, "55+": 0, "?": 0}
    # Expression construite une seule fois et réutilisée. PostgreSQL exige que
    # l'expression du GROUP BY soit textuellement identique à celle du SELECT ;
    # deux appels distincts produiraient des paramètres liés numérotés
    # différemment, et la requête serait rejetée. SQLite l'acceptait, si bien
    # que le défaut ne serait apparu qu'une fois le site déployé.
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

    # Top villes
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
            {"number": o.number, "email": o.email, "total_cents": o.total_cents,
             "created_at": o.created_at.isoformat(), "status": o.status}
            for o in recent_orders
        ],
        "demographics": {
            "civility": civility_counts,
            "age_buckets": age_buckets,
            "top_cities": [{"city": c, "count": n} for c, n in top_cities],
        },
    }


# ------------------------------------------------------------------ #
# Analytique                                                          #
# ------------------------------------------------------------------ #
#
# Quatre routes plutot qu'une seule. La vue d'ensemble est consultee a chaque
# ouverture du tableau de bord ; les cohortes, la segmentation et l'analyse de
# panier sont des vues que l'on ouvre a dessein, et qui coutent plus cher a
# calculer. Les servir ensemble ferait payer a tout le monde ce que peu
# consultent, et interdirait de les mettre en cache separement.
#
# Les calculs eux-memes vivent dans `app/analytics.py` : ces fonctions ne font
# que valider les parametres et rendre le resultat.


@router.get("/analytics")
def analytics_overview(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    months: int = Query(12, ge=3, le=36),
    days: int = Query(30, ge=7, le=365, description="Fenetre de comparaison, en jours"),
):
    """Vue d'ensemble : periode courante, periode precedente, catalogue."""
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
        "top_customers": analytics.top_customers(db),
    }


@router.get("/analytics/audience")
def analytics_audience(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    city: str | None = Query(None, max_length=120),
    age: str | None = Query(None, max_length=10),
    civility: str | None = Query(None, max_length=2),
):
    """Portrait d'achat d'un segment demographique.

    Les trois criteres se cumulent et sont tous facultatifs : sans filtre, la
    reponse decrit l'ensemble de la clientele, ce qui donne le point de
    comparaison sans lequel le chiffre d'un segment ne veut rien dire.
    """
    return analytics.audience_profile(db, city=city, age=age, civility=civility)


@router.get("/analytics/forecast")
def analytics_forecast(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    months: int = Query(12, ge=6, le=36),
    horizon: int = Query(3, ge=1, le=6),
):
    """Tendance du chiffre d'affaires et projection a court terme."""
    return analytics.forecast(db, months, horizon)


@router.get("/analytics/cohorts")
def analytics_cohorts(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    months: int = Query(12, ge=3, le=24),
):
    """Retention par cohorte d'inscription."""
    return analytics.cohorts(db, months)


@router.get("/analytics/segments")
def analytics_segments(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    """Segmentation RFM de la clientele acheteuse."""
    return analytics.rfm_segments(db)


@router.get("/analytics/affinities")
def analytics_affinities(
    db: Session = Depends(get_db),
    _=Depends(get_admin_user),
    limit: int = Query(12, ge=3, le=50),
):
    """Produits frequemment achetes ensemble, classes par lift."""
    return analytics.affinities(db, limit)


# ------------------------------------------------------------------ #
# Produits                                                            #
# ------------------------------------------------------------------ #
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
    for field, val in data.model_dump(exclude_none=True).items():
        if field == "images":
            setattr(p, "images", json.dumps(val))
        else:
            setattr(p, field, val)
    db.commit(); db.refresh(p)
    return _prod_dict(p)


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    p = db.get(models.Product, product_id)
    if not p:
        raise HTTPException(404, "Produit introuvable.")
    # Desactivation douce : ne pas supprimer si des commandes existent
    has_orders = db.query(models.OrderItem).filter(models.OrderItem.product_id == product_id).first()
    if has_orders:
        p.active = False
    else:
        db.delete(p)
    db.commit()


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


# ------------------------------------------------------------------ #
# Codes promo                                                         #
# ------------------------------------------------------------------ #
@router.get("/promos")
def list_promos(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    return db.query(models.Promo).order_by(models.Promo.id).all()


@router.post("/promos", status_code=201)
def create_promo(data: PromoIn, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    if db.query(models.Promo).filter(models.Promo.code == data.code.upper()).first():
        raise HTTPException(409, "Ce code existe déjà.")
    promo = models.Promo(
        code=data.code.strip().upper(), kind=data.kind, percent=data.percent,
        amount_cents=data.amount_cents, min_subtotal_cents=data.min_subtotal_cents,
        active=data.active, expires_at=data.expires_at,
    )
    db.add(promo); db.commit(); db.refresh(promo)
    return promo


@router.patch("/promos/{promo_id}")
def update_promo(promo_id: int, data: PromoIn, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    promo = db.get(models.Promo, promo_id)
    if not promo:
        raise HTTPException(404, "Code promo introuvable.")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(promo, field, val)
    db.commit(); db.refresh(promo)
    return promo


@router.delete("/promos/{promo_id}", status_code=204)
def delete_promo(promo_id: int, db: Session = Depends(get_db), _=Depends(get_admin_writer)):
    promo = db.get(models.Promo, promo_id)
    if not promo:
        raise HTTPException(404, "Code promo introuvable.")
    db.delete(promo); db.commit()


# ------------------------------------------------------------------ #
# Commandes                                                           #
# ------------------------------------------------------------------ #
@router.get("/orders")
def list_orders(
    db: Session = Depends(get_db), _=Depends(get_admin_user),
    limit: int = Query(50, le=200), offset: int = 0,
):
    orders = db.query(models.Order).order_by(
        models.Order.created_at.desc()
    ).offset(offset).limit(limit).all()
    return [
        {"number": o.number, "email": o.email, "status": o.status,
         "total_cents": o.total_cents, "created_at": o.created_at.isoformat(),
         "items": [{"name": i.name, "qty": i.qty, "unit_price_cents": i.unit_price_cents} for i in o.items]}
        for o in orders
    ]


@router.get("/orders.csv")
def export_orders_csv(
    db: Session = Depends(get_db), _=Depends(get_admin_user),
    status_val: str | None = Query(None, alias="status"),
):
    """Exporte les commandes en CSV, pour la comptabilite et les expeditions.

    Une ligne par article et non par commande : c'est la forme directement
    exploitable dans un tableur, ou l'on veut sommer des quantites par produit.
    Le numero de commande sert de cle de regroupement.

    Les montants sont exportes en euros avec un separateur decimal virgule, et
    le fichier est prefixe d'un BOM UTF-8. Sans ces deux precautions, Excel en
    configuration francaise ouvre le fichier avec les accents casses et les
    montants traites comme du texte.
    """
    query = db.query(models.Order).order_by(models.Order.created_at.desc())
    if status_val:
        query = query.filter(models.Order.status == status_val)

    buffer = io.StringIO()
    # QUOTE_ALL : une adresse ou un nom de produit contenant un point-virgule
    # ne doit pas decaler les colonnes.
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
                order.number,
                order.created_at.isoformat(timespec="seconds"),
                order.status,
                order.email,
                item.name,
                item.qty,
                eur(item.unit_price_cents),
                eur(item.unit_price_cents * item.qty),
                eur(order.total_cents),
                eur(order.discount_cents),
                eur(order.shipping_cents),
                order.promo_code or "",
            ])

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        # utf-8-sig ajoute le BOM que reclame Excel.
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="hanabi-commandes-{stamp}.csv"'},
    )


@router.patch("/orders/{number}/status")
def update_order_status(
    number: str, status_val: str = Query(..., alias="status"),
    db: Session = Depends(get_db), _=Depends(get_admin_writer),
):
    allowed = {"paid", "shipped", "delivered", "cancelled", "refunded"}
    if status_val not in allowed:
        raise HTTPException(422, f"Statut invalide. Valeurs : {', '.join(allowed)}")
    order = db.query(models.Order).filter(models.Order.number == number).first()
    if not order:
        raise HTTPException(404, "Commande introuvable.")
    order.status = status_val
    db.commit()
    return {"number": order.number, "status": order.status}


# ------------------------------------------------------------------ #
# Utilisateurs                                                        #
# ------------------------------------------------------------------ #
@router.get("/users")
def list_users(
    db: Session = Depends(get_db), _=Depends(get_admin_user),
    q: str | None = Query(None, description="Filtre sur le nom, l'e-mail ou la ville"),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
):
    """Liste paginee des clients, avec leur historique d'achat agrege.

    Deux corrections par rapport a la version precedente, toutes deux devenues
    indispensables des lors que la base compte des milliers de comptes :

    - la pagination. Renvoyer la table entiere, c'etait construire dix mille
      objets JSON pour en afficher trente a l'ecran ;
    - le calcul du nombre de commandes et du total depense en une seule
      jointure agregee, au lieu d'une requete par client. L'ancienne boucle
      emettait autant de requetes qu'il y avait de lignes - le cas d'ecole du
      probleme dit « N+1 », invisible sur douze comptes de demonstration et
      redhibitoire ensuite.
    """
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

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            AdminUserOut(
                id=u.id, name=u.name, email=u.email, civility=u.civility,
                birthdate=u.birthdate, city=u.city, is_admin=u.is_admin,
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


# ------------------------------------------------------------------ #
# Alertes stock                                                       #
# ------------------------------------------------------------------ #
@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db), _=Depends(get_admin_user)):
    alerts = db.query(models.StockAlert).filter(
        models.StockAlert.notified.is_(False)
    ).all()
    return [
        {"id": a.id, "product_id": a.product_id, "email": a.email, "created_at": a.created_at.isoformat()}
        for a in alerts
    ]