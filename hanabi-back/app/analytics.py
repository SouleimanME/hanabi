# -*- coding: utf-8 -*-
"""Calculs du back-office sur la base transactionnelle.

Requêtes portables SQLite et PostgreSQL : ni `date_trunc` ni `strftime`, le
regroupement mensuel prend les sept premiers caractères de la date ISO
(`_month_key`). Les agrégations lourdes restent en base ; seuls le classement RFM
et les règles d'association passent en Python.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import String, cast, distinct, func, literal_column, select
from sqlalchemy.orm import Session

from . import models

# Statuts comptés en chiffre d'affaires : une commande expédiée ou livrée est
# encaissée. À garder identique à `statuts_ca` dans hanabi-dwh/dbt_project.yml.
REVENUE_STATUSES = ("paid", "shipped", "delivered")


# --- Outils communs ---
# Bornes littérales plutôt que paramètres liés : PostgreSQL exige un GROUP BY
# textuellement identique au SELECT, et SQLAlchemy numérote chaque paramètre.
_DEBUT = literal_column("1")
_LONGUEUR_MOIS = literal_column("7")


def _month_key(column):
    """« AAAA-MM » d'une colonne date, identique sur SQLite et PostgreSQL."""
    return func.substr(cast(column, String), _DEBUT, _LONGUEUR_MOIS)


def _as_utc(value: datetime | None) -> datetime | None:
    """Date relue ramenée à UTC (SQLite rend des valeurs naïves)."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _last_months(count: int, reference: datetime | None = None) -> list[str]:
    """Les `count` derniers mois, du plus ancien au plus récent, mois vides compris."""
    today = reference or datetime.now(timezone.utc)
    year, month = today.year, today.month
    keys: list[str] = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _month_offset(depart: str, arrivee: str) -> int:
    """Nombre de mois entre deux clés « AAAA-MM »."""
    a_annee, a_mois = int(depart[:4]), int(depart[5:7])
    b_annee, b_mois = int(arrivee[:4]), int(arrivee[5:7])
    return (b_annee - a_annee) * 12 + (b_mois - a_mois)


def _variation(courant: float, precedent: float) -> float | None:
    """Évolution relative ; `None` si la période précédente est nulle."""
    if precedent == 0:
        return None
    return round((courant - precedent) / precedent, 4)


# --- Vue d'ensemble ---
def _window_metrics(db: Session, debut: datetime, fin: datetime) -> dict:
    """Indicateurs d'une fenêtre temporelle, toutes mesures sur les mêmes bornes."""
    encaisse, commandes, remise = db.execute(
        select(
            func.coalesce(func.sum(models.Order.total_cents), 0),
            func.count(models.Order.id),
            func.coalesce(func.sum(models.Order.discount_cents), 0),
        ).where(
            models.Order.status.in_(REVENUE_STATUSES),
            models.Order.created_at >= debut,
            models.Order.created_at < fin,
        )
    ).one()

    vues = db.execute(
        select(func.count(models.ProductView.id)).where(
            models.ProductView.created_at >= debut, models.ProductView.created_at < fin
        )
    ).scalar() or 0

    inscriptions = db.execute(
        select(func.count(models.User.id)).where(
            models.User.created_at >= debut, models.User.created_at < fin
        )
    ).scalar() or 0

    acheteurs = db.execute(
        select(func.count(distinct(models.Order.user_id))).where(
            models.Order.status.in_(REVENUE_STATUSES),
            models.Order.user_id.isnot(None),
            models.Order.created_at >= debut,
            models.Order.created_at < fin,
        )
    ).scalar() or 0

    articles = db.execute(
        select(func.coalesce(func.sum(models.OrderItem.qty), 0))
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .where(
            models.Order.status.in_(REVENUE_STATUSES),
            models.Order.created_at >= debut,
            models.Order.created_at < fin,
        )
    ).scalar() or 0

    commandes = int(commandes)
    encaisse = int(encaisse)
    return {
        "revenue_cents": encaisse,
        "orders": commandes,
        "aov_cents": round(encaisse / commandes) if commandes else 0,
        "views": int(vues),
        "signups": int(inscriptions),
        "buyers": int(acheteurs),
        "units": int(articles),
        "discount_cents": int(remise),
        "conversion": round(commandes / vues, 4) if vues else 0.0,
        "items_per_order": round(articles / commandes, 2) if commandes else 0.0,
        # Revenu par fiche consultée : audience et panier en un nombre
        "revenue_per_view_cents": round(encaisse / vues) if vues else 0,
    }


def period_overview(db: Session, days: int) -> dict:
    """Indicateurs de la période, comparés à la période précédente de même durée.

    Neutralise la durée, pas la saisonnalité.
    """
    fin = datetime.now(timezone.utc)
    debut = fin - timedelta(days=days)
    debut_precedent = debut - timedelta(days=days)

    courant = _window_metrics(db, debut, fin)
    precedent = _window_metrics(db, debut_precedent, debut)

    return {
        "days": days,
        "from": debut.isoformat(),
        "to": fin.isoformat(),
        "current": courant,
        "previous": precedent,
        "change": {cle: _variation(courant[cle], precedent[cle]) for cle in courant},
    }


def lifetime_kpis(db: Session) -> dict:
    """Indicateurs depuis l'origine (réachat et part d'acheteurs n'ont de sens que là)."""
    encaisse = db.execute(
        select(func.coalesce(func.sum(models.Order.total_cents), 0)).where(
            models.Order.status.in_(REVENUE_STATUSES)
        )
    ).scalar() or 0
    commandes = db.execute(
        select(func.count(models.Order.id)).where(models.Order.status.in_(REVENUE_STATUSES))
    ).scalar() or 0
    clients = db.execute(select(func.count(models.User.id))).scalar() or 0
    vues = db.execute(select(func.count(models.ProductView.id))).scalar() or 0

    par_client = (
        select(models.Order.user_id, func.count(models.Order.id).label("n"))
        .where(models.Order.status.in_(REVENUE_STATUSES), models.Order.user_id.isnot(None))
        .group_by(models.Order.user_id)
        .subquery()
    )
    acheteurs = db.execute(select(func.count()).select_from(par_client)).scalar() or 0
    fideles = db.execute(
        select(func.count()).select_from(par_client).where(par_client.c.n > 1)
    ).scalar() or 0

    return {
        "revenue_cents": int(encaisse),
        "orders": int(commandes),
        "customers": int(clients),
        "views": int(vues),
        "buyers": int(acheteurs),
        "aov_cents": round(encaisse / commandes) if commandes else 0,
        "conversion": round(commandes / vues, 4) if vues else 0.0,
        "buyer_rate": round(acheteurs / clients, 4) if clients else 0.0,
        "repeat_rate": round(fideles / acheteurs, 4) if acheteurs else 0.0,
        # Plancher de la valeur vie client
        "revenue_per_buyer_cents": round(encaisse / acheteurs) if acheteurs else 0,
    }


# --- Séries mensuelles ---
def monthly_series(db: Session, months: int) -> list[dict]:
    cles = _last_months(months)
    depuis = cles[0]

    mois_commande = _month_key(models.Order.created_at)
    ventes = {
        m: (int(n), int(ca or 0))
        for m, n, ca in db.execute(
            select(mois_commande, func.count(models.Order.id), func.sum(models.Order.total_cents))
            .where(models.Order.status.in_(REVENUE_STATUSES), mois_commande >= depuis)
            .group_by(mois_commande)
        ).all()
    }
    mois_inscription = _month_key(models.User.created_at)
    inscriptions = dict(db.execute(
        select(mois_inscription, func.count(models.User.id))
        .where(mois_inscription >= depuis)
        .group_by(mois_inscription)
    ).all())
    mois_vue = _month_key(models.ProductView.created_at)
    vues = dict(db.execute(
        select(mois_vue, func.count(models.ProductView.id))
        .where(mois_vue >= depuis)
        .group_by(mois_vue)
    ).all())

    return [
        {
            "month": cle,
            "revenue_cents": ventes.get(cle, (0, 0))[1],
            "orders": ventes.get(cle, (0, 0))[0],
            "signups": int(inscriptions.get(cle, 0)),
            "views": int(vues.get(cle, 0)),
        }
        for cle in cles
    ]


# --- Catalogue ---
def catalogue(db: Session) -> list[dict]:
    """Une ligne par référence : audience, ventes, marge, stock, avis. Non trié."""
    vues = dict(db.execute(
        select(models.ProductView.product_id, func.count(models.ProductView.id))
        .group_by(models.ProductView.product_id)
    ).all())

    # count(distinct order_id) : trois exemplaires d'un article font une commande
    ventes = {
        pid: {
            "units": int(units or 0),
            "revenue_cents": int(ca or 0),
            # Sur prix et coût figés dans les lignes de commande
            "margin_cents": int((ca or 0) - (cout or 0)),
            "orders": int(n or 0),
            "last_order_at": derniere.isoformat() if derniere else None,
        }
        for pid, units, ca, cout, n, derniere in db.execute(
            select(
                models.OrderItem.product_id,
                func.sum(models.OrderItem.qty),
                func.sum(models.OrderItem.qty * models.OrderItem.unit_price_cents),
                func.sum(models.OrderItem.qty * models.OrderItem.unit_cost_cents),
                func.count(distinct(models.OrderItem.order_id)),
                func.max(models.Order.created_at),
            )
            .join(models.Order, models.OrderItem.order_id == models.Order.id)
            .where(models.Order.status.in_(REVENUE_STATUSES))
            .group_by(models.OrderItem.product_id)
        ).all()
    }

    notes = {
        pid: (round(float(moyenne or 0), 2), int(n or 0))
        for pid, moyenne, n in db.execute(
            select(
                models.Review.product_id,
                func.avg(models.Review.rating),
                func.count(models.Review.id),
            )
            .where(models.Review.approved.is_(True))
            .group_by(models.Review.product_id)
        ).all()
    }

    vide = {
        "units": 0, "revenue_cents": 0, "margin_cents": 0,
        "orders": 0, "last_order_at": None,
    }

    # Vitesse d'écoulement sur 90 jours, pour refléter le rythme actuel
    depuis = datetime.now(timezone.utc) - timedelta(days=90)
    recentes = dict(db.execute(
        select(models.OrderItem.product_id, func.sum(models.OrderItem.qty))
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .where(
            models.Order.status.in_(REVENUE_STATUSES),
            models.Order.created_at >= depuis,
        )
        .group_by(models.OrderItem.product_id)
    ).all())

    lignes = []
    for p in db.scalars(select(models.Product).order_by(models.Product.id)):
        v = vues.get(p.id, 0)
        s = ventes.get(p.id, vide)
        # Une série retirée sans vente n'a rien à dire ; vendue, elle reste dans l'historique
        if not p.active and not s["units"]:
            continue
        note, nb_avis = notes.get(p.id, (0.0, 0))

        marge_unitaire = p.price_cents - p.cost_cents
        par_jour = int(recentes.get(p.id, 0)) / 90

        lignes.append({
            "id": p.id, "code": p.code, "name": p.name, "category": p.category,
            "price_cents": p.price_cents, "cost_cents": p.cost_cents,
            "stock": p.stock, "active": p.active,
            "views": v,
            "units": s["units"],
            "orders": s["orders"],
            "revenue_cents": s["revenue_cents"],
            "margin_cents": s["margin_cents"],
            # Nul sans coût renseigné (et non 100 %)
            "margin_rate": (
                round(s["margin_cents"] / s["revenue_cents"], 4)
                if s["revenue_cents"] and p.cost_cents else 0.0
            ),
            "unit_margin_cents": marge_unitaire if p.cost_cents else 0,
            # Commandes par consultation ; nul sans consultation
            "conversion": round(s["orders"] / v, 4) if v else 0.0,
            # Jours de vente couverts par le stock ; `None` si la référence ne se vend plus
            "days_of_stock": round(p.stock / par_jour, 1) if par_jour > 0 else None,
            "daily_velocity": round(par_jour, 2),
            "rating_avg": note,
            "rating_count": nb_avis,
            "last_order_at": s["last_order_at"],
        })

    return _with_abc(lignes)


def _with_abc(lignes: list[dict]) -> list[dict]:
    """Classement ABC sur la marge : 80 % du cumul en A, 15 % en B, le reste en C."""
    total = sum(l["margin_cents"] for l in lignes)
    if total <= 0:
        for ligne in lignes:
            ligne["abc"] = "C"
            ligne["margin_share"] = 0.0
            ligne["cumulative_share"] = 0.0
        return lignes

    cumul = 0.0
    for ligne in sorted(lignes, key=lambda l: -l["margin_cents"]):
        part = ligne["margin_cents"] / total
        # Classe décidée sur le cumul avant la référence : celle qui franchit
        # le seuil reste dans la classe qu'elle complète
        ligne["abc"] = "A" if cumul < 0.80 else ("B" if cumul < 0.95 else "C")
        cumul += part
        ligne["margin_share"] = round(part, 4)
        ligne["cumulative_share"] = round(cumul, 4)
    return lignes


def categories(db: Session, produits: list[dict]) -> list[dict]:
    vide = {"revenue_cents": 0, "margin_cents": 0, "units": 0, "views": 0}
    ventes = {
        cat: {
            "revenue_cents": int(ca or 0),
            "margin_cents": int((ca or 0) - (cout or 0)),
            "units": int(units or 0),
            "views": 0,
        }
        for cat, units, ca, cout in db.execute(
            select(
                models.Product.category,
                func.sum(models.OrderItem.qty),
                func.sum(models.OrderItem.qty * models.OrderItem.unit_price_cents),
                func.sum(models.OrderItem.qty * models.OrderItem.unit_cost_cents),
            )
            .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)
            .join(models.Order, models.OrderItem.order_id == models.Order.id)
            .where(models.Order.status.in_(REVENUE_STATUSES))
            .group_by(models.Product.category)
        ).all()
    }
    for produit in produits:
        bloc = ventes.setdefault(produit["category"], dict(vide))
        bloc["views"] += produit["views"]
    return sorted(
        (
            {
                "category": cat,
                **bloc,
                "margin_rate": (
                    round(bloc["margin_cents"] / bloc["revenue_cents"], 4)
                    if bloc["revenue_cents"] else 0.0
                ),
            }
            for cat, bloc in ventes.items()
        ),
        key=lambda c: -c["revenue_cents"],
    )


def profitability(produits: list[dict]) -> dict:
    """Rentabilité : marge, classes ABC, ruptures à venir, écarts entre rang au CA et rang à la marge."""
    ca = sum(p["revenue_cents"] for p in produits)
    marge = sum(p["margin_cents"] for p in produits)

    par_ca = sorted(produits, key=lambda p: -p["revenue_cents"])
    par_marge = sorted(produits, key=lambda p: -p["margin_cents"])

    classes: dict[str, dict] = {}
    for produit in produits:
        bloc = classes.setdefault(
            produit.get("abc", "C"), {"references": 0, "margin_cents": 0, "revenue_cents": 0}
        )
        bloc["references"] += 1
        bloc["margin_cents"] += produit["margin_cents"]
        bloc["revenue_cents"] += produit["revenue_cents"]

    return {
        "revenue_cents": ca,
        "margin_cents": marge,
        "margin_rate": round(marge / ca, 4) if ca else 0.0,
        # Stock couvrant moins de trois semaines au rythme actuel
        "at_risk": [
            {
                "name": p["name"],
                "stock": p["stock"],
                "days_of_stock": p["days_of_stock"],
                "daily_velocity": p["daily_velocity"],
            }
            for p in sorted(
                (p for p in produits if p["days_of_stock"] is not None and p["days_of_stock"] < 21),
                key=lambda p: p["days_of_stock"],
            )
        ],
        # Écart de rang élevé : volume sans marge, ou l'inverse
        "rank_shifts": [
            {
                "name": p["name"],
                "revenue_rank": par_ca.index(p) + 1,
                "margin_rank": par_marge.index(p) + 1,
                "shift": par_ca.index(p) - par_marge.index(p),
                "margin_rate": p["margin_rate"],
            }
            for p in sorted(produits, key=lambda p: -abs(par_ca.index(p) - par_marge.index(p)))[:5]
        ],
        "abc": [
            {"classe": cle, **classes[cle]} for cle in sorted(classes) if classes.get(cle)
        ],
    }


def promo_performance(db: Session) -> list[dict]:
    return [
        {
            "code": code,
            "orders": int(n),
            "revenue_cents": int(ca or 0),
            "discount_cents": int(remise or 0),
        }
        for code, n, ca, remise in db.execute(
            select(
                models.Order.promo_code,
                func.count(models.Order.id),
                func.sum(models.Order.total_cents),
                func.sum(models.Order.discount_cents),
            )
            .where(
                models.Order.status.in_(REVENUE_STATUSES),
                models.Order.promo_code.isnot(None),
            )
            .group_by(models.Order.promo_code)
            .order_by(func.count(models.Order.id).desc())
        ).all()
    ]


def status_breakdown(db: Session) -> list[dict]:
    return [
        {"status": statut, "count": int(n)}
        for statut, n in db.execute(
            select(models.Order.status, func.count(models.Order.id))
            .group_by(models.Order.status)
            .order_by(func.count(models.Order.id).desc())
        ).all()
    ]


def top_customers(db: Session, limit: int = 10) -> list[dict]:
    return [
        {
            "id": uid, "name": nom, "email": mail, "city": ville,
            "orders": int(n), "total_cents": int(total or 0),
        }
        for uid, nom, mail, ville, n, total in db.execute(
            select(
                models.User.id, models.User.name, models.User.email, models.User.city,
                func.count(models.Order.id), func.sum(models.Order.total_cents),
            )
            .join(models.Order, models.Order.user_id == models.User.id)
            .where(models.Order.status.in_(REVENUE_STATUSES))
            .group_by(models.User.id)
            .order_by(func.sum(models.Order.total_cents).desc())
            .limit(limit)
        ).all()
    ]


# --- Tendance et prévision ---
def _regression(valeurs: list[float]) -> tuple[float, float, float]:
    """Moindres carrés sur une série mensuelle régulière : (pente, origine, R²)."""
    n = len(valeurs)
    if n < 2:
        return 0.0, valeurs[0] if valeurs else 0.0, 0.0

    xs = list(range(n))
    moyenne_x = sum(xs) / n
    moyenne_y = sum(valeurs) / n

    variance_x = sum((x - moyenne_x) ** 2 for x in xs)
    if variance_x == 0:
        return 0.0, moyenne_y, 0.0

    covariance = sum((x - moyenne_x) * (y - moyenne_y) for x, y in zip(xs, valeurs))
    pente = covariance / variance_x
    origine = moyenne_y - pente * moyenne_x

    # R² = 1 - somme des carrés résiduels / somme des carrés totaux
    residus = sum((y - (pente * x + origine)) ** 2 for x, y in zip(xs, valeurs))
    total = sum((y - moyenne_y) ** 2 for y in valeurs)
    r2 = 1 - residus / total if total else 0.0

    return pente, origine, r2


def _cmgr(debut: float, fin: float, periodes: int) -> float | None:
    """Taux de croissance mensuel composé ; `None` si la série part de zéro."""
    if debut <= 0 or periodes <= 0:
        return None
    return round((fin / debut) ** (1 / periodes) - 1, 4)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Corrélation de Pearson ; `None` si une série ne varie pas. Pas une causalité."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None

    moyenne_x = sum(xs) / n
    moyenne_y = sum(ys) / n
    covariance = sum((x - moyenne_x) * (y - moyenne_y) for x, y in zip(xs, ys))
    ecart_x = sum((x - moyenne_x) ** 2 for x in xs) ** 0.5
    ecart_y = sum((y - moyenne_y) ** 2 for y in ys) ** 0.5

    if ecart_x == 0 or ecart_y == 0:
        return None
    return round(covariance / (ecart_x * ecart_y), 3)


def forecast(db: Session, months: int = 12, horizon: int = 3) -> dict:
    """Tendance du chiffre d'affaires et projection à court terme.

    Droite de tendance avec R², taux de croissance mensuel composé et indice de
    saisonnalité. Projection limitée à quelques mois.
    """
    serie = monthly_series(db, months)
    valeurs = [m["revenue_cents"] for m in serie]

    # Les mois vides en tête de série précèdent l'ouverture : exclus de la pente
    premier = next((i for i, v in enumerate(valeurs) if v > 0), None)
    if premier is None:
        return {
            "months": months, "horizon": horizon, "trend": None,
            "projection": [], "cmgr": None, "seasonality": [],
        }

    utiles = valeurs[premier:]
    mois_utiles = [m["month"] for m in serie[premier:]]
    pente, origine, r2 = _regression([float(v) for v in utiles])

    # Prolonge la droite après le dernier point
    n = len(utiles)
    annee, mois = int(mois_utiles[-1][:4]), int(mois_utiles[-1][5:7])
    projection = []
    for pas in range(1, horizon + 1):
        mois += 1
        if mois == 13:
            annee, mois = annee + 1, 1
        valeur = pente * (n - 1 + pas) + origine
        projection.append({
            "month": f"{annee:04d}-{mois:02d}",
            # Jamais négative
            "revenue_cents": max(0, round(valeur)),
        })

    # Moyenne de chaque mois calendaire rapportée à la moyenne générale ;
    # indicatif tant que chaque mois n'est observé qu'une fois
    par_mois: dict[int, list[int]] = {}
    for point in serie[premier:]:
        par_mois.setdefault(int(point["month"][5:7]), []).append(point["revenue_cents"])
    moyenne_generale = sum(utiles) / len(utiles) if utiles else 0
    saisonnalite = [
        {
            "month": numero,
            "index": round((sum(v) / len(v)) / moyenne_generale, 3) if moyenne_generale else 0.0,
            "observations": len(v),
        }
        for numero, v in sorted(par_mois.items())
    ]

    return {
        "months": months,
        "horizon": horizon,
        "trend": {
            "slope_cents_per_month": round(pente),
            "r2": round(r2, 3),
            "from": mois_utiles[0],
            "to": mois_utiles[-1],
        },
        "history": [
            {"month": m, "revenue_cents": v} for m, v in zip(mois_utiles, utiles)
        ],
        "projection": projection,
        "cmgr": _cmgr(utiles[0], utiles[-1], len(utiles) - 1),
        "seasonality": saisonnalite,
    }


def audience_correlation(produits: list[dict]) -> dict:
    """Corrélation entre audience des fiches et ventes, puis marge."""
    vues = [float(p["views"]) for p in produits]
    unites = [float(p["units"]) for p in produits]
    marges = [float(p["margin_cents"]) for p in produits]
    return {
        "views_units": _pearson(vues, unites),
        "views_margin": _pearson(vues, marges),
        "products": len(produits),
    }


# --- Cohortes ---
def cohorts(db: Session, months: int = 12) -> dict:
    """Rétention par cohorte d'inscription.

    Mois 0 : conversion à l'inscription ; suivants : fidélisation. Les mois pas
    encore advenus valent `None`, pas zéro.
    """
    cles = _last_months(months)
    depuis = cles[0]
    aujourd_hui = _last_months(1)[0]

    mois_inscription = _month_key(models.User.created_at)
    tailles = dict(db.execute(
        select(mois_inscription, func.count(models.User.id))
        .where(mois_inscription >= depuis)
        .group_by(mois_inscription)
    ).all())

    # Un client compte une fois par mois de commande
    activite = db.execute(
        select(
            _month_key(models.User.created_at),
            _month_key(models.Order.created_at),
            func.count(distinct(models.Order.user_id)),
        )
        .join(models.Order, models.Order.user_id == models.User.id)
        .where(
            models.Order.status.in_(REVENUE_STATUSES),
            _month_key(models.User.created_at) >= depuis,
        )
        .group_by(_month_key(models.User.created_at), _month_key(models.Order.created_at))
    ).all()

    matrice: dict[str, dict[int, int]] = {}
    for cohorte, mois, actifs in activite:
        decalage = _month_offset(cohorte, mois)
        if decalage < 0:
            # Commande antérieure à l'inscription (invitée rattachée après coup)
            continue
        matrice.setdefault(cohorte, {})[decalage] = int(actifs)

    lignes = []
    for cohorte in cles:
        taille = int(tailles.get(cohorte, 0))
        maximum = _month_offset(cohorte, aujourd_hui)
        cellules = []
        for decalage in range(months):
            if decalage > maximum:
                # Mois pas encore advenu
                cellules.append(None)
                continue
            actifs = matrice.get(cohorte, {}).get(decalage, 0)
            cellules.append({
                "active": actifs,
                "rate": round(actifs / taille, 4) if taille else 0.0,
            })
        lignes.append({"cohort": cohorte, "size": taille, "cells": cellules})

    return {"months": months, "rows": lignes}


# --- Segmentation RFM ---
# Scores de 1 à 5 par quintile, relatifs aux autres clients
RFM_QUINTILES = 5


def _score_par_rang(valeurs: list[float], croissant: bool) -> dict[float, int]:
    """Score de 1 à 5 par quintile de population.

    Les ex aequo partagent leur score, fixé au rang médian de leur groupe. Classer
    les valeurs distinctes donnait R=5 à 73 % des acheteurs et vidait « À risque ».
    Un groupe d'ex aequo plus gros qu'un quintile ne se répartit pas.

    Doit rester identique à `gold_clients_rfm.sql` dans hanabi-dwh.
    """
    if not valeurs:
        return {}

    effectifs: dict[float, int] = {}
    for valeur in valeurs:
        effectifs[valeur] = effectifs.get(valeur, 0) + 1

    total = len(valeurs)
    scores: dict[float, int] = {}
    cumul = 0
    # Meilleur en premier : récence croissante, fréquence et montant décroissants
    for valeur in sorted(effectifs, reverse=not croissant):
        poids = effectifs[valeur]
        # Milieu du groupe dans la population, entre 0 et 1
        milieu = (cumul + poids / 2) / total
        quintile = min(RFM_QUINTILES - 1, int(milieu * RFM_QUINTILES))
        scores[valeur] = RFM_QUINTILES - quintile
        cumul += poids
    return scores


def _segment(recence: int, frequence: int, montant: int, commandes: int) -> str:
    """Segment à partir des trois scores et du nombre réel de commandes.

    Une seule commande, même grosse et récente, fait un client nouveau, pas fidèle.
    """
    valeur = (frequence + montant) / 2
    if commandes >= 2 and recence >= 4 and valeur >= 4:
        return "Champions"
    if commandes >= 2 and recence >= 3 and valeur >= 3:
        return "Fideles"
    if commandes == 1 and recence >= 4:
        return "Nouveaux"
    if recence >= 3:
        return "Prometteurs"
    if valeur >= 3:
        # Bon client qui ne revient plus
        return "A risque"
    if valeur <= 2 and recence <= 2:
        return "Endormis"
    return "A reactiver"


SEGMENT_ORDER = [
    "Champions", "Fideles", "Prometteurs", "Nouveaux",
    "A risque", "A reactiver", "Endormis",
]


def rfm_segments(db: Session) -> dict:
    """Segmentation RFM des acheteurs ; les non-acheteurs sont comptés à part.

    Scores relatifs : sans effectif suffisant, les quintiles ne séparent plus rien.
    """
    lignes = db.execute(
        select(
            models.User.id,
            models.User.name,
            models.User.email,
            models.User.city,
            func.max(models.Order.created_at),
            func.count(models.Order.id),
            func.sum(models.Order.total_cents),
        )
        .join(models.Order, models.Order.user_id == models.User.id)
        .where(models.Order.status.in_(REVENUE_STATUSES))
        .group_by(models.User.id)
    ).all()

    total_clients = db.execute(select(func.count(models.User.id))).scalar() or 0

    if not lignes:
        return {
            "segments": [],
            "customers": 0,
            "non_buyers": int(total_clients),
            "examples": [],
        }

    maintenant = datetime.now(timezone.utc)
    clients = []
    for uid, nom, mail, ville, derniere, n, total in lignes:
        derniere = _as_utc(derniere)
        clients.append({
            "id": uid, "name": nom, "email": mail, "city": ville,
            # Jours de calendrier, comme `current_date - date` dans l'entrepôt
            "recency_days": max(0, (maintenant.date() - derniere.date()).days) if derniere else 9999,
            "frequency": int(n),
            "monetary_cents": int(total or 0),
        })

    # Récence : plus petit vaut mieux
    score_r = _score_par_rang([c["recency_days"] for c in clients], croissant=True)
    score_f = _score_par_rang([c["frequency"] for c in clients], croissant=False)
    score_m = _score_par_rang([c["monetary_cents"] for c in clients], croissant=False)

    for c in clients:
        c["r"] = score_r[c["recency_days"]]
        c["f"] = score_f[c["frequency"]]
        c["m"] = score_m[c["monetary_cents"]]
        c["segment"] = _segment(c["r"], c["f"], c["m"], c["frequency"])

    groupes: dict[str, list[dict]] = {}
    for c in clients:
        groupes.setdefault(c["segment"], []).append(c)

    ca_total = sum(c["monetary_cents"] for c in clients) or 1
    segments = []
    for nom_segment in SEGMENT_ORDER:
        membres = groupes.get(nom_segment, [])
        if not membres:
            continue
        ca = sum(c["monetary_cents"] for c in membres)
        segments.append({
            "segment": nom_segment,
            "customers": len(membres),
            "share": round(len(membres) / len(clients), 4),
            "revenue_cents": ca,
            # À comparer au poids du segment dans la clientèle
            "revenue_share": round(ca / ca_total, 4),
            "avg_value_cents": round(ca / len(membres)),
            "avg_orders": round(sum(c["frequency"] for c in membres) / len(membres), 2),
            "avg_recency_days": round(sum(c["recency_days"] for c in membres) / len(membres)),
        })

    # Trois clients par segment
    exemples = []
    for segment in segments:
        membres = sorted(
            groupes[segment["segment"]], key=lambda c: -c["monetary_cents"]
        )[:3]
        for c in membres:
            exemples.append({
                "segment": segment["segment"],
                "name": c["name"], "email": c["email"], "city": c["city"],
                "recency_days": c["recency_days"],
                "frequency": c["frequency"],
                "monetary_cents": c["monetary_cents"],
                "scores": f"{c['r']}{c['f']}{c['m']}",
            })

    return {
        "segments": segments,
        "customers": len(clients),
        "non_buyers": int(total_clients) - len(clients),
        "examples": exemples,
    }


# --- Portrait d'un segment ---
# Tranches d'âge, alignées sur le tableau de bord et sur slv_clients
AGE_BUCKETS = {
    "<18": (0, 17),
    "18-24": (18, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55+": (55, 120),
}


def _annee_naissance():
    """Année de naissance ; expression unique pour SELECT et GROUP BY."""
    return func.substr(models.User.birthdate, _DEBUT, literal_column("4"))


def audience_profile(
    db: Session,
    *,
    city: str | None = None,
    age: str | None = None,
    civility: str | None = None,
    limit: int = 5,
) -> dict:
    """Portrait d'achat d'un segment démographique.

    Critères cumulables et facultatifs ; sans filtre, toute la clientèle sert de référence.
    """
    conditions = []
    if city:
        conditions.append(models.User.city == city)
    if civility:
        # « ? » : civilité non renseignée
        conditions.append(
            models.User.civility.is_(None) if civility == "?" else models.User.civility == civility
        )
    if age and age in AGE_BUCKETS:
        mini, maxi = AGE_BUCKETS[age]
        aujourd_hui = datetime.now(timezone.utc).year
        # Âge à un an près, comme le tableau de bord
        conditions.append(
            cast(_annee_naissance(), String).between(
                str(aujourd_hui - maxi), str(aujourd_hui - mini)
            )
        )

    membres = select(models.User.id)
    if conditions:
        membres = membres.where(*conditions)
    membres = membres.subquery()

    clients = db.execute(select(func.count()).select_from(membres)).scalar() or 0
    if clients == 0:
        return {
            "filters": {"city": city, "age": age, "civility": civility},
            "customers": 0, "buyers": 0, "revenue_cents": 0, "aov_cents": 0,
            "orders": 0, "buyer_rate": 0.0,
            "top_products": [], "best_customer": None, "biggest_order": None,
        }

    commandes = (
        select(models.Order)
        .join(membres, membres.c.id == models.Order.user_id)
        .where(models.Order.status.in_(REVENUE_STATUSES))
        .subquery()
    )

    total, nombre, acheteurs = db.execute(
        select(
            func.coalesce(func.sum(commandes.c.total_cents), 0),
            func.count(commandes.c.id),
            func.count(distinct(commandes.c.user_id)),
        )
    ).one()
    nombre = int(nombre)
    total = int(total)

    top = [
        {"name": nom, "units": int(u or 0), "revenue_cents": int(ca or 0)}
        for nom, u, ca in db.execute(
            select(
                models.Product.name,
                func.sum(models.OrderItem.qty),
                func.sum(models.OrderItem.qty * models.OrderItem.unit_price_cents),
            )
            .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)
            .join(commandes, commandes.c.id == models.OrderItem.order_id)
            .group_by(models.Product.name)
            .order_by(func.sum(models.OrderItem.qty).desc())
            .limit(limit)
        ).all()
    ]

    meilleur = db.execute(
        select(
            models.User.name, models.User.email, models.User.city,
            func.count(commandes.c.id), func.sum(commandes.c.total_cents),
        )
        .join(commandes, commandes.c.user_id == models.User.id)
        .group_by(models.User.id)
        .order_by(func.sum(commandes.c.total_cents).desc())
        .limit(1)
    ).first()

    grosse = db.execute(
        select(
            commandes.c.number, commandes.c.total_cents,
            commandes.c.created_at, commandes.c.email,
        )
        .order_by(commandes.c.total_cents.desc())
        .limit(1)
    ).first()

    return {
        "filters": {"city": city, "age": age, "civility": civility},
        "customers": clients,
        "buyers": int(acheteurs),
        "buyer_rate": round(int(acheteurs) / clients, 4),
        "orders": nombre,
        "revenue_cents": total,
        "aov_cents": round(total / nombre) if nombre else 0,
        # Par client du segment, acheteurs ou non : compare des segments de tailles différentes
        "value_per_customer_cents": round(total / clients),
        "top_products": top,
        "best_customer": (
            {
                "name": meilleur[0], "email": meilleur[1], "city": meilleur[2],
                "orders": int(meilleur[3]), "total_cents": int(meilleur[4] or 0),
            }
            if meilleur else None
        ),
        "biggest_order": (
            {
                "number": grosse[0],
                "total_cents": int(grosse[1]),
                "created_at": grosse[2].isoformat() if grosse[2] else None,
                "email": grosse[3],
            }
            if grosse else None
        ),
    }


# --- Affinités ---
def affinities(db: Session, limit: int = 12) -> dict:
    """Règles d'association entre produits.

    Support : part des commandes contenant la paire. Confiance A vers B : part des
    commandes avec A qui contiennent B. Lift : confiance rapportée à la fréquence de
    B ; au-dessus de 1, les articles se complètent. Tri par lift, avec un support
    minimal. L'auto-jointure `a < b` produit chaque paire une fois.
    """
    total_commandes = db.execute(
        select(func.count(models.Order.id)).where(models.Order.status.in_(REVENUE_STATUSES))
    ).scalar() or 0

    if total_commandes == 0:
        return {"pairs": [], "orders": 0, "min_support_orders": 0}

    par_produit = dict(db.execute(
        select(models.OrderItem.product_id, func.count(distinct(models.OrderItem.order_id)))
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .where(models.Order.status.in_(REVENUE_STATUSES))
        .group_by(models.OrderItem.product_id)
    ).all())

    a = models.OrderItem.__table__.alias("a")
    b = models.OrderItem.__table__.alias("b")
    paires = db.execute(
        select(a.c.product_id, b.c.product_id, func.count(distinct(a.c.order_id)))
        .select_from(
            a.join(b, (a.c.order_id == b.c.order_id) & (a.c.product_id < b.c.product_id))
            .join(models.Order.__table__, models.Order.id == a.c.order_id)
        )
        .where(models.Order.status.in_(REVENUE_STATUSES))
        .group_by(a.c.product_id, b.c.product_id)
    ).all()

    noms = dict(db.execute(select(models.Product.id, models.Product.name)).all())

    # Seuil de bruit : 1 % des commandes, cinq au minimum
    seuil = max(5, total_commandes // 100)

    regles = []
    for pid_a, pid_b, ensemble in paires:
        ensemble = int(ensemble)
        if ensemble < seuil:
            continue
        n_a = int(par_produit.get(pid_a, 0))
        n_b = int(par_produit.get(pid_b, 0))
        if not n_a or not n_b:
            continue
        support = ensemble / total_commandes
        confiance_ab = ensemble / n_a
        confiance_ba = ensemble / n_b
        lift = confiance_ab / (n_b / total_commandes)
        regles.append({
            "a_id": pid_a, "a_name": noms.get(pid_a, "?"),
            "b_id": pid_b, "b_name": noms.get(pid_b, "?"),
            "orders_together": ensemble,
            "support": round(support, 4),
            "confidence_ab": round(confiance_ab, 4),
            "confidence_ba": round(confiance_ba, 4),
            "lift": round(lift, 3),
        })

    regles.sort(key=lambda r: -r["lift"])
    return {
        "pairs": regles[:limit],
        "orders": int(total_commandes),
        "min_support_orders": seuil,
    }
