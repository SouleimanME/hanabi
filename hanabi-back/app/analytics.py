# -*- coding: utf-8 -*-
"""Calculs decisionnels du back-office.

Sorti du routeur pour trois raisons. Ces fonctions sont testables sans passer
par HTTP ; elles se lisent comme une bibliotheque d'analyses plutot que comme
des poignees d'API ; et le decoupage force a nommer chaque indicateur, ce qui
est la moitie du travail dans un tableau de bord.

Portabilite. La suite de tests tourne sur SQLite, la production sur PostgreSQL.
Aucune fonction propre a un moteur n'est utilisee : pas de `date_trunc`, pas de
`strftime`. Le regroupement mensuel passe par les sept premiers caracteres de la
date ecrite en texte, forme ISO commune aux deux moteurs (voir `_month_key`).

Volumetrie. Le catalogue compte une douzaine de references et la clientele
quelques milliers de comptes. Les agregations lourdes sont faites par la base,
et seul le resultat - quelques milliers de lignes au plus - est repris en
Python la ou la logique serait illisible en SQL : le classement RFM et les
regles d'association. Sur un catalogue de plusieurs milliers de references, ce
dernier calcul devrait redescendre en SQL, voire dans une table precalculee.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import String, cast, distinct, func, literal_column, select
from sqlalchemy.orm import Session

from . import models

# Statuts qui comptent comme du chiffre d'affaires realise.
#
# Une commande expediee ou livree a bel et bien ete encaissee : ne retenir que
# « payee » revenait a effacer du tableau de bord toute commande dont le statut
# avait avance, et donc a faire baisser le chiffre d'affaires a mesure que les
# colis partaient. Seules les annulations et les remboursements en sortent.
REVENUE_STATUSES = ("paid", "shipped", "delivered")


# ------------------------------------------------------------------ #
# Outils communs                                                      #
# ------------------------------------------------------------------ #
# Bornes de decoupage ecrites en dur dans le SQL plutot que passees en
# parametres lies. La raison n'est pas la performance mais la correction.
#
# PostgreSQL exige qu'une expression du GROUP BY soit textuellement identique a
# celle du SELECT. Avec des parametres lies, SQLAlchemy numerote chaque
# occurrence separement : le SELECT recoit `substr(x, $2, $3)` et le GROUP BY
# `substr(x, $10, $11)`. Le moteur n'y voit pas la meme expression et refuse la
# requete. SQLite, plus permissif, l'acceptait - le defaut ne se voyait donc
# qu'une fois deploye.
_DEBUT = literal_column("1")
_LONGUEUR_MOIS = literal_column("7")


def _month_key(column):
    """Extrait « AAAA-MM » d'une colonne date, sans fonction propre a un moteur.

    `strftime` n'existe que sur SQLite et `to_char` que sur PostgreSQL : utiliser
    l'une des deux enfermerait le regroupement mensuel dans le moteur du moment.
    Or les deux ecrivent une date en texte ISO, qui commence par l'annee et le
    mois - les sept premiers caracteres suffisent donc, quel que soit le moteur.
    """
    return func.substr(cast(column, String), _DEBUT, _LONGUEUR_MOIS)


def _as_utc(value: datetime | None) -> datetime | None:
    """Ramene une date relue en UTC, qu'elle porte ou non un fuseau.

    SQLite n'a pas de type date natif et rend des valeurs naives, PostgreSQL
    rend des valeurs situees. Comparer les deux formes leve un TypeError ; on
    considere une valeur naive comme deja exprimee en UTC, ce qui correspond a
    ce que l'application ecrit.
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _last_months(count: int, reference: datetime | None = None) -> list[str]:
    """Suite des `count` derniers mois, du plus ancien au plus recent.

    Construite independamment des donnees : un mois sans commande doit
    apparaitre a zero dans la serie, sinon la courbe se resserre en sautant les
    creux et laisse croire a une activite continue.
    """
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
    """Nombre de mois entre deux cles « AAAA-MM »."""
    a_annee, a_mois = int(depart[:4]), int(depart[5:7])
    b_annee, b_mois = int(arrivee[:4]), int(arrivee[5:7])
    return (b_annee - a_annee) * 12 + (b_mois - a_mois)


def _variation(courant: float, precedent: float) -> float | None:
    """Evolution relative entre deux periodes.

    `None` lorsque la periode precedente est vide : une progression depuis zero
    n'est pas un pourcentage. Afficher « +100 % » ou « +∞ » dans ce cas serait
    faux, et masquer la ligne ferait disparaitre l'information.
    """
    if precedent == 0:
        return None
    return round((courant - precedent) / precedent, 4)


# ------------------------------------------------------------------ #
# Vue d'ensemble, avec comparaison de periode                         #
# ------------------------------------------------------------------ #
def _window_metrics(db: Session, debut: datetime, fin: datetime) -> dict:
    """Indicateurs d'une fenetre temporelle.

    Toutes les mesures partagent les memes bornes, faute de quoi la comparaison
    entre deux periodes n'aurait pas de sens.
    """
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
        # Ce que rapporte une fiche consultee. Rapproche l'audience du chiffre
        # d'affaires en un seul nombre : deux boutiques peuvent avoir le meme
        # taux de conversion et des paniers tres differents.
        "revenue_per_view_cents": round(encaisse / vues) if vues else 0,
    }


def period_overview(db: Session, days: int) -> dict:
    """Indicateurs de la periode, compares a la periode precedente de meme duree.

    Un chiffre isole ne dit pas s'il est bon. La comparaison a la fenetre
    immediatement anterieure, de duree identique, est la lecture la plus honnete
    sans donnees de reference exterieures : elle neutralise la taille de la
    periode, mais pas la saisonnalite, ce qu'une comparaison annuelle ferait -
    l'historique genere ici ne couvre pas assez d'annees pour la proposer.
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
    """Indicateurs depuis l'origine, independants de la periode choisie.

    Le taux de reachat et la part de clients acheteurs n'ont de sens que sur
    tout l'historique : mesures sur trente jours, ils diraient surtout combien
    de clients anciens ont commande ce mois-ci.
    """
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
        # Revenu moyen par acheteur, toutes commandes confondues. Plancher de la
        # valeur vie client : il ne prejuge pas des achats a venir.
        "revenue_per_buyer_cents": round(encaisse / acheteurs) if acheteurs else 0,
    }


# ------------------------------------------------------------------ #
# Series mensuelles                                                   #
# ------------------------------------------------------------------ #
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


# ------------------------------------------------------------------ #
# Catalogue                                                           #
# ------------------------------------------------------------------ #
def catalogue(db: Session) -> list[dict]:
    """Une ligne par reference : audience, ventes, conversion, satisfaction.

    Renvoye brut, non trie. Les questions « les plus vus », « les moins
    commandes », « ceux qui ne se vendent pas » sont autant de tris de la meme
    matiere : les figer cote serveur reviendrait a decider a la place de
    l'interface, sur un jeu de douze lignes.
    """
    vues = dict(db.execute(
        select(models.ProductView.product_id, func.count(models.ProductView.id))
        .group_by(models.ProductView.product_id)
    ).all())

    # `count(distinct order_id)` et non `count(*)` : une commande de trois
    # exemplaires du meme article reste une commande. Confondre les deux
    # gonflerait le taux de conversion des produits achetes par lot.
    ventes = {
        pid: {
            "units": int(units or 0),
            "revenue_cents": int(ca or 0),
            # Marge brute reelle : elle s'appuie sur le prix et le cout figes
            # dans chaque ligne de commande, pas sur les valeurs courantes de la
            # fiche. Un changement de tarif ne doit pas reecrire le resultat des
            # mois deja clos.
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

    # Vitesse d'ecoulement, mesuree sur les quatre-vingt-dix derniers jours
    # plutot que sur tout l'historique : la couverture de stock doit refleter le
    # rythme actuel, pas la moyenne depuis l'ouverture de la boutique.
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
            # Taux de marge sur le chiffre d'affaires realise. Nul si aucun cout
            # n'est renseigne : afficher 100 % ferait passer une fiche mal
            # remplie pour la plus rentable du catalogue.
            "margin_rate": (
                round(s["margin_cents"] / s["revenue_cents"], 4)
                if s["revenue_cents"] and p.cost_cents else 0.0
            ),
            "unit_margin_cents": marge_unitaire if p.cost_cents else 0,
            # Part des consultations qui aboutissent a une commande. Nul si la
            # fiche n'a jamais ete ouverte : diviser par zero n'aurait pas de
            # sens, et afficher 100 % en serait un contresens.
            "conversion": round(s["orders"] / v, 4) if v else 0.0,
            # Nombre de jours de vente que le stock couvre encore, au rythme des
            # quatre-vingt-dix derniers jours. `None` quand la reference ne se
            # vend plus du tout : la couverture est alors infinie, ce qui est un
            # probleme d'une autre nature qu'une rupture imminente.
            "days_of_stock": round(p.stock / par_jour, 1) if par_jour > 0 else None,
            "daily_velocity": round(par_jour, 2),
            "rating_avg": note,
            "rating_count": nb_avis,
            "last_order_at": s["last_order_at"],
        })

    return _with_abc(lignes)


def _with_abc(lignes: list[dict]) -> list[dict]:
    """Classe les references en A, B et C selon la loi de Pareto.

    Les references sont triees par marge decroissante, puis leur contribution
    est cumulee : celles qui produisent les 80 premiers pour cent forment la
    classe A, les 15 suivants la classe B, le reste la classe C.

    Le tri se fait sur la marge et non sur le chiffre d'affaires, parce que
    c'est la marge qui paie les charges. Un article a fort volume et faible
    marge remplit le classement des ventes sans rien rapporter, et le classer A
    conduirait a lui consacrer les efforts de reapprovisionnement.
    """
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
        # La classe se decide sur le cumul atteint AVANT cette reference, pas
        # apres. Autrement, celle qui fait franchir le seuil se retrouve exclue
        # de la classe qu'elle vient de remplir : un catalogue ou un seul
        # produit pese 85 % de la marge n'aurait aucune reference en A, ce qui
        # est le contraire de ce que l'analyse cherche a montrer.
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
    """Vue d'ensemble de la rentabilite, et ce qu'elle change au classement.

    L'ecart entre le podium du chiffre d'affaires et celui de la marge est
    l'information principale : c'est lui qui dit ou l'argent est reellement
    gagne, et il est invisible tant qu'on ne regarde que les ventes.
    """
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
        # Les references dont le stock couvre moins de trois semaines de vente
        # au rythme actuel : ce sont les ruptures a venir.
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
        # Le meme catalogue, classe deux fois. Un ecart de rang eleve signale
        # une reference qui fait du volume sans rapporter, ou l'inverse.
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


# ------------------------------------------------------------------ #
# Tendance et prevision                                               #
# ------------------------------------------------------------------ #
def _regression(valeurs: list[float]) -> tuple[float, float, float]:
    """Droite des moindres carres sur une serie reguliere.

    Renvoie (pente, ordonnee a l'origine, coefficient de determination).

    L'abscisse est le rang du mois, ce qui suppose des intervalles reguliers -
    vrai ici puisque la serie est construite mois par mois, trous compris.

    Le coefficient de determination compte autant que la pente : il dit quelle
    part de la variation la droite explique. Une tendance annoncee sans lui est
    un chiffre sans garantie, et c'est exactement ainsi que l'on projette des
    droites sur des donnees qui n'en suivent aucune.
    """
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

    # R² = 1 - somme des carres residuels / somme des carres totaux.
    residus = sum((y - (pente * x + origine)) ** 2 for x, y in zip(xs, valeurs))
    total = sum((y - moyenne_y) ** 2 for y in valeurs)
    r2 = 1 - residus / total if total else 0.0

    return pente, origine, r2


def _cmgr(debut: float, fin: float, periodes: int) -> float | None:
    """Taux de croissance mensuel compose.

    Lisse la croissance sur toute la periode, la ou une comparaison entre deux
    mois isoles depend entierement du choix de ces deux mois. `None` si la
    serie part de zero : aucun taux ne mene de zero a une valeur positive.
    """
    if debut <= 0 or periodes <= 0:
        return None
    return round((fin / debut) ** (1 / periodes) - 1, 4)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Coefficient de correlation lineaire entre deux series.

    Vaut 1 quand les deux varient exactement ensemble, 0 quand elles n'ont
    aucun lien lineaire, -1 quand elles s'opposent. `None` si l'une des deux ne
    varie pas, auquel cas la question n'a pas de sens.

    A ne pas lire comme une causalite : une correlation forte entre audience et
    ventes ne dit pas laquelle entraine l'autre.
    """
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
    """Tendance du chiffre d'affaires et projection a court terme.

    Trois lectures complementaires de la meme serie :

    - la **droite de tendance**, qui donne la progression moyenne par mois et
      la part de la variation qu'elle explique ;
    - le **taux de croissance mensuel compose**, qui lisse la progression du
      premier au dernier mois sans dependre du choix de deux mois isoles ;
    - l'**indice de saisonnalite**, qui rapporte chaque mois calendaire a la
      moyenne. Sans lui, on attribue a la tendance ce qui n'est qu'un creux
      d'ete ou un pic de fin d'annee.

    La projection est volontairement bornee a quelques mois et accompagnee de
    son R². Une extrapolation lineaire sur une boutique en croissance vaut ce
    que vaut l'hypothese que rien ne change - c'est-a-dire pas grand-chose
    au-dela d'un trimestre.
    """
    serie = monthly_series(db, months)
    valeurs = [m["revenue_cents"] for m in serie]

    # Les mois sans aucune vente en tete de serie ne sont pas des mois faibles :
    # ce sont des mois ou la boutique n'existait pas encore. Les inclure
    # ecraserait la pente vers le bas.
    premier = next((i for i, v in enumerate(valeurs) if v > 0), None)
    if premier is None:
        return {
            "months": months, "horizon": horizon, "trend": None,
            "projection": [], "cmgr": None, "seasonality": [],
        }

    utiles = valeurs[premier:]
    mois_utiles = [m["month"] for m in serie[premier:]]
    pente, origine, r2 = _regression([float(v) for v in utiles])

    # Projection : on prolonge la droite au-dela du dernier point connu.
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
            # Une projection negative n'a pas de sens commercial : on la ramene
            # a zero plutot que d'afficher un chiffre d'affaires negatif.
            "revenue_cents": max(0, round(valeur)),
        })

    # Saisonnalite : moyenne de chaque mois calendaire rapportee a la moyenne
    # generale. Sur douze mois d'historique, chaque mois n'est observe qu'une
    # fois - l'indice est donc indicatif, et le devient vraiment au-dela de
    # deux ans.
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
    """Lien entre l'audience d'une fiche et ses ventes.

    Un seul nombre pour trancher une question de fond : l'audience se
    transforme-t-elle en commandes ? Un coefficient eleve indique que faire
    venir du monde suffit ; un coefficient faible indique que le probleme est
    ailleurs, dans le prix ou dans la fiche elle-meme.
    """
    vues = [float(p["views"]) for p in produits]
    unites = [float(p["units"]) for p in produits]
    marges = [float(p["margin_cents"]) for p in produits]
    return {
        "views_units": _pearson(vues, unites),
        "views_margin": _pearson(vues, marges),
        "products": len(produits),
    }


# ------------------------------------------------------------------ #
# Cohortes et retention                                               #
# ------------------------------------------------------------------ #
def cohorts(db: Session, months: int = 12) -> dict:
    """Retention par cohorte d'inscription.

    Chaque ligne rassemble les comptes crees un meme mois ; chaque colonne
    compte ceux qui ont commande N mois plus tard. C'est la seule vue qui
    distingue une croissance saine d'une fuite en avant : une boutique qui
    recrute beaucoup et retient mal affiche une courbe de chiffre d'affaires
    flatteuse et des colonnes qui s'effondrent des le premier mois.

    Le mois 0 mesure la conversion a l'inscription, les suivants la
    fidelisation. Les cases situees dans le futur d'une cohorte recente sont
    nulles et non pas zero : une cohorte d'un mois n'a pas encore eu l'occasion
    de revenir six mois plus tard, et l'afficher a zero la ferait passer pour un
    echec.
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

    # Activite : un client compte une fois par mois ou il a commande.
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
            # Une commande anterieure a l'inscription : impossible en principe,
            # mais une commande invitee rattachee apres coup le produirait.
            continue
        matrice.setdefault(cohorte, {})[decalage] = int(actifs)

    lignes = []
    for cohorte in cles:
        taille = int(tailles.get(cohorte, 0))
        maximum = _month_offset(cohorte, aujourd_hui)
        cellules = []
        for decalage in range(months):
            if decalage > maximum:
                # Mois pas encore advenu pour cette cohorte.
                cellules.append(None)
                continue
            actifs = matrice.get(cohorte, {}).get(decalage, 0)
            cellules.append({
                "active": actifs,
                "rate": round(actifs / taille, 4) if taille else 0.0,
            })
        lignes.append({"cohort": cohorte, "size": taille, "cells": cellules})

    return {"months": months, "rows": lignes}


# ------------------------------------------------------------------ #
# Segmentation RFM                                                    #
# ------------------------------------------------------------------ #
# Bornes des scores, en quintiles. Un client est note de 1 a 5 sur chacun des
# trois axes par rapport aux autres clients, et non dans l'absolu : les seuils
# d'une boutique de luxe et d'une boutique a petits prix n'ont rien de commun,
# et figer des montants en dur rendrait la segmentation fausse ailleurs.
RFM_QUINTILES = 5


def _score_par_rang(valeurs: list[float], croissant: bool) -> dict[float, int]:
    """Associe a chaque valeur un score de 1 a 5, par quintile de population.

    Deux exigences, longtemps difficiles a tenir ensemble :

    1. **Les ex aequo partagent leur score.** Deux clients ayant exactement le
       meme montant doivent etre notes pareil, sinon leur rang dependrait de
       l'ordre dans lequel la base a rendu les lignes - un score qui change
       d'une lecture a l'autre n'est pas un score.
    2. **Les quintiles decoupent la population, pas l'echelle des valeurs.**
       « Etre dans le premier quintile » veut dire « faire partie des 20 % de
       clients les mieux places », c'est le sens usuel du mot et ce qu'un
       lecteur comprendra.

    La version precedente ne tenait que la premiere. Elle classait les *valeurs
    distinctes* : avec 679 anciennetes differentes reparties sur deux ans, un
    score de recence a 5 signifiait « dans les 136 premieres valeurs de
    l'echelle », pas « parmi les 20 % de clients les plus recents ». Comme la
    clientele est concentree sur les achats recents, 73 % des acheteurs
    obtenaient 5, et les segments batis sur une mauvaise recence - « A risque »,
    « A reactiver » - se vidaient : dix-neuf personnes sur trente-quatre mille,
    la ou la relance a pourtant le plus de valeur.

    On note donc chaque valeur par le **rang median de son groupe d'ex aequo**,
    exprime en part de la population. Un groupe se voit attribuer la position de
    son milieu plutot que celle de son debut ou de sa fin : c'est la convention
    des rangs moyens, et elle evite qu'un gros paquet d'ex aequo - la moitie des
    clients n'ont commande qu'une fois - soit juge sur son extremite la plus
    defavorable.

    Limite qui demeure, et qu'aucune methode ne leve : un groupe d'ex aequo plus
    gros qu'un quintile ne peut pas etre reparti. Si 55 % des clients ont
    exactement une commande, ces 55 % partagent forcement un score de frequence.
    C'est une propriete de la donnee, pas du calcul.
    """
    if not valeurs:
        return {}

    effectifs: dict[float, int] = {}
    for valeur in valeurs:
        effectifs[valeur] = effectifs.get(valeur, 0) + 1

    total = len(valeurs)
    scores: dict[float, int] = {}
    cumul = 0
    # Meilleur en premier : recence croissante (recent = bien), frequence et
    # montant decroissants (beaucoup = bien).
    for valeur in sorted(effectifs, reverse=not croissant):
        poids = effectifs[valeur]
        # Position du milieu du groupe dans la population, entre 0 et 1.
        milieu = (cumul + poids / 2) / total
        quintile = min(RFM_QUINTILES - 1, int(milieu * RFM_QUINTILES))
        scores[valeur] = RFM_QUINTILES - quintile
        cumul += poids
    return scores


def _segment(recence: int, frequence: int, montant: int, commandes: int) -> str:
    """Nomme un segment a partir des trois scores.

    Decoupage volontairement grossier et lisible : sept segments qu'une equipe
    marketing peut s'approprier, la ou les 125 combinaisons possibles ne se
    lisent pas. Les frontieres sont celles couramment retenues, pas une verite.

    Le nombre reel de commandes intervient a cote du score de frequence. Un
    client venu une seule fois, meme pour un gros montant recent, n'est pas
    fidele : il est nouveau. Se fier au seul score de frequence le classait
    parmi les fideles des lors que son montant tirait la moyenne vers le haut,
    ce qui gonflait artificiellement le segment le plus flatteur.
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
        # Bon client qui ne revient plus : c'est ici que la relance a le plus
        # de valeur, puisqu'il a deja prouve qu'il achetait.
        return "A risque"
    if valeur <= 2 and recence <= 2:
        return "Endormis"
    return "A reactiver"


SEGMENT_ORDER = [
    "Champions", "Fideles", "Prometteurs", "Nouveaux",
    "A risque", "A reactiver", "Endormis",
]


def rfm_segments(db: Session) -> dict:
    """Segmentation Recence / Frequence / Montant de la clientele acheteuse.

    Repose sur trois questions : quand ce client a-t-il commande pour la
    derniere fois, combien de fois, et pour quel montant. Le croisement des
    trois separe le client fidele du client unique venu par une promotion, ce
    qu'aucun total ne montre.

    Les non-acheteurs sont exclus : ils n'ont ni recence ni montant, et les
    inclure ecraserait la distribution. Leur nombre est renvoye a part.

    Limite a connaitre : les scores sont relatifs, donc la segmentation n'a de
    sens que sur une population suffisante. Sur une dizaine d'acheteurs, les
    quintiles ne separent plus rien - un client parti depuis un an peut obtenir
    un bon score de recence faute de comparaison. Ce n'est pas un defaut du
    calcul mais sa nature : ce qu'il mesure, c'est un rang parmi les autres
    clients, et un rang parmi trois personnes ne veut rien dire.
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
            # Ecart de dates de calendrier, et non nombre de tranches de 24 h
            # ecoulees. Une commande passee hier a 22 h doit compter pour un
            # jour ; `(maintenant - derniere).days` la comptait pour zero, ce qui
            # faisait dependre la recence de l'heure de la commande autant que de
            # sa date. L'entrepot calcule `current_date - date`, soit exactement
            # cette convention : les deux chemins classaient sinon une poignee de
            # clients differemment, et deux segmentations qui divergent d'un
            # onglet a l'autre ne sont credibles ni l'une ni l'autre.
            "recency_days": max(0, (maintenant.date() - derniere.date()).days) if derniere else 9999,
            "frequency": int(n),
            "monetary_cents": int(total or 0),
        })

    # Recence : plus c'est petit, mieux c'est, d'ou le tri croissant.
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
            # Part du chiffre d'affaires : c'est l'ecart entre cette part et le
            # poids demographique du segment qui justifie d'y consacrer des
            # moyens.
            "revenue_share": round(ca / ca_total, 4),
            "avg_value_cents": round(ca / len(membres)),
            "avg_orders": round(sum(c["frequency"] for c in membres) / len(membres), 2),
            "avg_recency_days": round(sum(c["recency_days"] for c in membres) / len(membres)),
        })

    # Quelques clients par segment, pour rendre la vue concrete.
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


# ------------------------------------------------------------------ #
# Exploration d'un segment d'audience                                 #
# ------------------------------------------------------------------ #
# Tranches d'age, en annees revolues. Doivent rester alignees sur celles du
# tableau de bord : deux decoupages differents pour la meme population
# donneraient deux histogrammes contradictoires.
AGE_BUCKETS = {
    "<18": (0, 17),
    "18-24": (18, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55+": (55, 120),
}


def _annee_naissance():
    """Annee de naissance, extraite du champ texte.

    Expression construite une seule fois et reutilisee : PostgreSQL exige que
    l'expression d'un GROUP BY soit textuellement identique a celle du SELECT,
    et deux appels distincts produiraient des parametres numerotes
    differemment.
    """
    return func.substr(models.User.birthdate, _DEBUT, literal_column("4"))


def audience_profile(
    db: Session,
    *,
    city: str | None = None,
    age: str | None = None,
    civility: str | None = None,
    limit: int = 5,
) -> dict:
    """Portrait d'achat d'un segment demographique.

    Repond a la question que pose naturellement un histogramme : « ces
    clients-la, qu'achetent-ils ? ». Un graphique de repartition dit combien ils
    sont ; il ne dit pas ce qu'ils valent, et c'est pourtant la seule chose qui
    justifie de leur parler.

    Les trois criteres se cumulent. Aucun d'eux n'est obligatoire : sans filtre,
    la fonction decrit l'ensemble de la clientele, ce qui donne le point de
    comparaison sans lequel un chiffre de segment ne veut rien dire.
    """
    conditions = []
    if city:
        conditions.append(models.User.city == city)
    if civility:
        # « ? » designe les comptes sans civilite renseignee : c'est une
        # information en soi, pas une absence a masquer.
        conditions.append(
            models.User.civility.is_(None) if civility == "?" else models.User.civility == civility
        )
    if age and age in AGE_BUCKETS:
        mini, maxi = AGE_BUCKETS[age]
        aujourd_hui = datetime.now(timezone.utc).year
        # Age deduit de l'annee seule, a un an pres : le meme raccourci que le
        # tableau de bord, pour que les deux vues comptent la meme chose.
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
        # Valeur moyenne par client du segment, acheteurs et non-acheteurs
        # confondus : c'est elle qui permet de comparer deux segments de taille
        # differente, la ou le chiffre d'affaires brut favorise toujours le plus
        # nombreux.
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


# ------------------------------------------------------------------ #
# Analyse de panier                                                   #
# ------------------------------------------------------------------ #
def affinities(db: Session, limit: int = 12) -> dict:
    """Regles d'association entre produits, sur les lignes de commande.

    Trois mesures, qui ne disent pas la meme chose :

    - le **support** est la part des commandes contenant les deux articles.
      Il dit si la regle est frequente, pas si elle est interessante ;
    - la **confiance** de A vers B est la part des commandes contenant A qui
      contiennent aussi B. Elle se laisse tromper par les articles populaires :
      tout se vend avec le best-seller ;
    - le **lift** corrige ce biais en rapportant la confiance a la frequence de
      B seul. Au-dessus de 1, les deux articles s'achetent ensemble plus
      souvent que le hasard ne le voudrait ; en dessous, ils se substituent
      l'un a l'autre.

    Seul le lift merite d'etre trie, et c'est pourquoi les paires sont classees
    dessus. Un support minimal ecarte les coincidences : sur une dizaine de
    commandes communes, un lift eleve ne veut rien dire.

    L'auto-jointure `a.product_id < b.product_id` ne produit chaque paire
    qu'une fois, dans un ordre stable. Elle coute le carre du nombre d'articles
    par commande, ce qui reste negligeable ici ou une commande depasse rarement
    trois lignes ; sur des paniers plus fournis, ce calcul devrait etre
    precalcule plutot que joue a chaque affichage.
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

    # Seuil de bruit : au moins 1 % des commandes, et jamais moins de cinq.
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
