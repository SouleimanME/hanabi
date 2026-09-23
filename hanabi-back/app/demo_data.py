# -*- coding: utf-8 -*-
"""Jeu de données de démonstration : clientèle, commandes, audience, avis.

- Déterministe : graine fixe, mêmes chiffres sur toute installation.
- Rapide : insertions par lots, un seul condensat bcrypt partagé.
- Cohérent : commandes postérieures aux inscriptions, totaux calculés comme
  `pricing.py`, audience et achats volontairement décorrélés.

Les comptes générés ne servent jamais à se connecter.
"""
from __future__ import annotations

import logging
import random
import unicodedata
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .pricing import FREE_SHIPPING_THRESHOLD_CENTS, SHIPPING_CENTS
from .security import hash_password

log = logging.getLogger("hanabi.demo")

# Graine du tirage : la changer modifie tous les chiffres
RANDOM_SEED = 20260731

# Profondeur de l'historique, en mois
HISTORY_MONTHS = 24

# Mot de passe commun aux comptes générés, jamais utilisé pour se connecter
FILLER_PASSWORD = "hanabi-demo-population-2026"

# Paramètres liés par instruction : borne de SQLite (32766), sous celle de PostgreSQL
MAX_PARAMS = 30_000

# Lignes par instruction, quel que soit le nombre de colonnes
MAX_ROWS = 5_000


# --- Vocabulaire ---
PRENOMS_M = [
    "Lucas", "Hugo", "Nathan", "Enzo", "Louis", "Gabriel", "Jules", "Arthur",
    "Raphaël", "Léo", "Adam", "Maël", "Paul", "Noah", "Ethan", "Tom", "Théo",
    "Sacha", "Antoine", "Baptiste", "Clément", "Maxime", "Nicolas", "Julien",
    "Thomas", "Alexandre", "Pierre", "Romain", "Quentin", "Florian", "Mehdi",
    "Yanis", "Samir", "Karim", "Bastien", "Victor", "Simon", "Mathis", "Axel",
    "Gaspard", "Côme", "Timothée", "Ilyes", "Rayan", "Souleymane", "Amine",
]
PRENOMS_F = [
    "Emma", "Jade", "Louise", "Alice", "Chloé", "Lina", "Rose", "Léa", "Manon",
    "Camille", "Sarah", "Inès", "Anna", "Julie", "Marie", "Clara", "Zoé", "Eva",
    "Lucie", "Charlotte", "Mathilde", "Océane", "Pauline", "Laura", "Élise",
    "Amandine", "Nina", "Margaux", "Claire", "Sofia", "Yasmine", "Aya",
    "Maëlys", "Juliette", "Agathe", "Romane", "Solène", "Lou", "Ambre", "Célia",
    "Nour", "Fatoumata", "Salomé", "Anaïs", "Justine",
]
# Prénoms épicènes, pour les comptes de civilité N
PRENOMS_N = ["Camille", "Alix", "Charlie", "Sasha", "Andréa", "Noa", "Swann", "Maxence"]

NOMS = [
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit",
    "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel",
    "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier", "Morel",
    "Girard", "André", "Lefèvre", "Mercier", "Dupont", "Lambert", "Bonnet",
    "François", "Martinez", "Legrand", "Garnier", "Faure", "Rousseau", "Blanc",
    "Guérin", "Muller", "Henry", "Roussel", "Nicolas", "Perrin", "Morin",
    "Mathieu", "Clément", "Gauthier", "Dumont", "Lopez", "Fontaine",
    "Chevalier", "Robin", "Masson", "Sanchez", "Gérard", "Nguyen", "Boyer",
    "Denis", "Lemaire", "Duval", "Joly", "Gautier", "Roger", "Roche", "Roy",
    "Noël", "Meyer", "Lucas", "Meunier", "Jean", "Perez", "Marchand", "Dufour",
    "Blanchard", "Barbier", "Brun", "Dumas", "Brunet", "Schmitt", "Leroux",
    "Colin", "Fernandez", "Renard", "Arnaud", "Rolland", "Caron", "Aubert",
    "Giraud", "Leclerc", "Vidal", "Bourgeois", "Renaud", "Lemoine", "Picard",
    "Gaillard", "Philippe", "Leclercq", "Lacroix", "Fabre", "Dupuis",
    "Traoré", "Diallo", "Benali", "Cohen", "Da Silva", "Ferreira",
]

# (ville, code postal, poids) : poids proches de la population des aires urbaines
VILLES = [
    ("Paris", "75011", 100), ("Marseille", "13006", 34), ("Lyon", "69003", 32),
    ("Toulouse", "31000", 26), ("Nice", "06000", 18), ("Nantes", "44000", 20),
    ("Montpellier", "34000", 17), ("Strasbourg", "67000", 16),
    ("Bordeaux", "33000", 21), ("Lille", "59000", 19), ("Rennes", "35000", 15),
    ("Reims", "51100", 10), ("Toulon", "83000", 9), ("Grenoble", "38000", 13),
    ("Dijon", "21000", 9), ("Angers", "49000", 9), ("Nîmes", "30000", 8),
    ("Villeurbanne", "69100", 8), ("Clermont-Ferrand", "63000", 8),
    ("Le Mans", "72000", 7), ("Aix-en-Provence", "13100", 8),
    ("Brest", "29200", 7), ("Tours", "37000", 7), ("Amiens", "80000", 6),
    ("Limoges", "87000", 6), ("Annecy", "74000", 6), ("Perpignan", "66000", 6),
    ("Besançon", "25000", 6), ("Metz", "57000", 6), ("Rouen", "76000", 7),
    ("Orléans", "45000", 6), ("Mulhouse", "68100", 5), ("Caen", "14000", 6),
    ("Nancy", "54000", 6), ("Argenteuil", "95100", 5), ("Roubaix", "59100", 5),
    ("Avignon", "84000", 5), ("La Rochelle", "17000", 5), ("Pau", "64000", 4),
    ("Bayonne", "64100", 4), ("Colmar", "68000", 4), ("Quimper", "29000", 4),
    ("Chambéry", "73000", 4), ("Biarritz", "64200", 3), ("Vannes", "56000", 3),
]

CODES_POSTAUX = {ville: cp for ville, cp, _ in VILLES}

RUES = [
    "rue des Lilas", "avenue Jean Jaurès", "rue de la République",
    "boulevard Victor Hugo", "rue Pasteur", "allée des Peupliers",
    "rue Gambetta", "avenue de la Gare", "rue du Moulin", "impasse des Rosiers",
    "rue Émile Zola", "cours Lafayette", "rue Saint-Martin", "quai des Chartrons",
    "rue de la Paix", "chemin des Vignes", "place du Marché", "rue Voltaire",
    "avenue Foch", "rue des Écoles", "rue Berthelot", "rue Carnot",
]

COMPLEMENTS = ["Bât. A", "Bât. B", "Appt 12", "Appt 3B", "2e étage", "Résidence Les Tilleuls"]

# Parts de marché approximatives des messageries en France
DOMAINES = [
    ("gmail.com", 42), ("orange.fr", 13), ("hotmail.fr", 9), ("outlook.fr", 8),
    ("free.fr", 7), ("yahoo.fr", 6), ("laposte.net", 5), ("sfr.fr", 4),
    ("wanadoo.fr", 3), ("icloud.com", 2), ("protonmail.com", 1),
]

# Poids d'audience et d'achat par produit, décorrélés : une lampe chère se
# regarde beaucoup et s'achète peu, un tenugui convertit bien.
POPULARITE = {
    # code       vues  achats
    "HNB-021": (100, 78),   # Lampe Torii : la vedette, forte sur les deux axes
    "HNB-026": (88, 21),    # Lampe Lune : très regardée, chère, convertit mal
    "HNB-052": (74, 40),    # Figurine Kitsune : nouveaute qui marche
    "HNB-014": (62, 55),    # Collier Maneki-neko : petit prix, bonne conversion
    "HNB-037": (55, 44),    # Eventail Sensu
    "HNB-033": (48, 62),    # Baguettes : peu regardees, achetees en complement
    "HNB-041": (44, 38),    # Bol a Ramen
    "HNB-045": (30, 52),    # Tenugui : le meilleur taux de transformation
    "HNB-008": (28, 24),    # Bandana Sushi
    "HNB-015": (24, 18),    # Gamelle Sakura
    "HNB-018": (16, 7),     # Maneki-neko dore : le fond de catalogue
    "HNB-009": (12, 4),     # Coussin Futon : cher et peu vu, invendu type
}
POPULARITE_DEFAUT = (20, 15)

# Ensembles d'articles achetés ensemble, pour que l'analyse de panier trouve
# des affinités (sinon tous les lifts restent proches de 1). Ils suivent des
# intentions d'achat plutôt que les catégories.
AFFINITES = [
    ["HNB-033", "HNB-041", "HNB-045"],            # le repas
    ["HNB-014", "HNB-008", "HNB-015", "HNB-009"],  # le compagnon
    ["HNB-021", "HNB-026", "HNB-052", "HNB-018"],  # l'ambiance
    ["HNB-037", "HNB-021", "HNB-045"],             # le cadeau, toutes categories
]

# Part des articles complémentaires tirés dans le même ensemble ; le reste
# vient de tout le catalogue
PART_AFFINITE = 0.62


# --- Outils de tirage ---
def _slug(value: str) -> str:
    """Prénom ou nom réduit à ce qui peut figurer dans une adresse."""
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return plain.lower().replace(" ", "-").replace("'", "")


def _weighted(rng: random.Random, items: list[tuple], count: int) -> list:
    """Tire `count` éléments parmi des couples (valeur, poids)."""
    values = [it[0] for it in items]
    weights = [it[-1] for it in items]
    return rng.choices(values, weights=weights, k=count)


def _recent_biased(
    rng: random.Random, start: datetime, end: datetime, courbure: float = 2.0
) -> datetime:
    """Date entre deux bornes, biaisée vers la fin (croissance de la boutique).

    `courbure` = 1 donne un tirage uniforme : les commandes s'en servent, car elles
    héritent déjà de la croissance des inscriptions.
    """
    span = (end - start).total_seconds()
    if span <= 0:
        return end
    # 1 - (1-u)^k : densité croissante
    u = rng.random()
    position = 1 - (1 - u) ** courbure
    # Saisonnalité : creux l'été, pic avant les fêtes
    moment = start + timedelta(seconds=span * position)
    if moment.month in (7, 8) and rng.random() < 0.35:
        moment -= timedelta(days=rng.randint(60, 120))
    elif moment.month in (11, 12) and rng.random() < 0.20:
        moment += timedelta(days=rng.randint(0, 20))
    return min(max(moment, start), end)


def _birthdate(rng: random.Random) -> str:
    """Date de naissance, cœur de cible entre 25 et 44 ans."""
    tranche = rng.choices(
        [(16, 17), (18, 24), (25, 34), (35, 44), (45, 54), (55, 72)],
        weights=[2, 17, 34, 25, 14, 8],
        k=1,
    )[0]
    age = rng.randint(*tranche)
    today = datetime.now(timezone.utc).date()
    # Âge retiré en jours pour répartir les anniversaires sur l'année
    naissance = today - timedelta(days=age * 365 + rng.randint(0, 364))
    return naissance.isoformat()


# --- Génération ---
def _bulk(db: Session, model, rows: list[dict]) -> None:
    """Insère des lignes par lots, une instruction `INSERT ... VALUES` par lot.

    `db.execute(insert(model), lot)` passerait par `executemany`, une instruction par
    ligne : immédiat sur SQLite, interminable sur une base distante.
    """
    if not rows:
        return

    colonnes = max(len(ligne) for ligne in rows)
    par_lot = max(1, min(MAX_ROWS, MAX_PARAMS // max(1, colonnes)))

    for debut in range(0, len(rows), par_lot):
        lot = rows[debut : debut + par_lot]
        db.execute(insert(model).values(lot))
    db.flush()


def _build_users(rng: random.Random, count: int, now: datetime, taken: set[str]) -> list[dict]:
    debut = now - timedelta(days=HISTORY_MONTHS * 30)
    mot_de_passe = hash_password(FILLER_PASSWORD)  # calcule une fois, voir en-tete

    villes = _weighted(rng, VILLES, count)
    domaines = _weighted(rng, DOMAINES, count)
    rows: list[dict] = []

    for i in range(count):
        # Répartition inégale et incomplète, comme une vraie base
        civilite = rng.choices(["F", "M", "N", None], weights=[48, 44, 3, 5], k=1)[0]
        if civilite == "F":
            prenom = rng.choice(PRENOMS_F)
        elif civilite == "M":
            prenom = rng.choice(PRENOMS_M)
        elif civilite == "N":
            prenom = rng.choice(PRENOMS_N)
        else:
            prenom = rng.choice(PRENOMS_F + PRENOMS_M)

        nom = rng.choice(NOMS)
        ville = villes[i]
        cp = CODES_POSTAUX[ville]

        base = f"{_slug(prenom)}.{_slug(nom)}"
        adresse = f"{base}@{domaines[i]}"
        # Homonymes numérotés
        if adresse in taken:
            adresse = f"{base}{rng.randint(2, 99)}.{i}@{domaines[i]}"
        taken.add(adresse)

        rows.append({
            "name": f"{prenom} {nom}",
            "email": adresse,
            "password_hash": mot_de_passe,
            "civility": civilite,
            # Un compte sur cinq sans date de naissance
            "birthdate": _birthdate(rng) if rng.random() > 0.20 else None,
            "phone": f"0{rng.choice([6, 7])}{rng.randint(10000000, 99999999)}",
            "addr": f"{rng.randint(1, 180)} {rng.choice(RUES)}",
            "addr_extra": rng.choice(COMPLEMENTS) if rng.random() < 0.25 else None,
            "cp": cp,
            "city": ville,
            "is_admin": False,
            "created_at": _recent_biased(rng, debut, now),
        })

    return rows


def _order_status(rng: random.Random, passee_le: datetime, now: datetime) -> str:
    """Statut cohérent avec l'ancienneté : livrée après douze jours, expédiée après trois."""
    jours = (now - passee_le).days
    tirage = rng.random()
    if tirage < 0.035:
        return "cancelled"
    if tirage < 0.055:
        return "refunded"
    if jours > 12:
        return "delivered"
    if jours > 3:
        return "shipped"
    return "paid"


def _build_orders(
    rng: random.Random,
    users: list[tuple[int, datetime]],
    produits: list[models.Product],
    promos: list[models.Promo],
    now: datetime,
) -> tuple[list[dict], list[tuple[int, int, int]], list[tuple[int, int]]]:
    """Commandes et lignes ; les lignes portent l'indice de commande, résolu après insertion."""
    poids_achat = [POPULARITE.get(p.code, POPULARITE_DEFAUT)[1] for p in produits]
    numeros: set[str] = set()

    # Ensembles d'affinité résolus en produits, indexés par produit meneur
    par_code = {p.code: p for p in produits}
    voisins: dict[int, list[list[models.Product]]] = {}
    for groupe in AFFINITES:
        membres = [par_code[c] for c in groupe if c in par_code]
        for membre in membres:
            voisins.setdefault(membre.id, []).append(membres)

    commandes: list[dict] = []
    # (indice de commande, product_id, qty)
    lignes: list[tuple[int, int, int]] = []
    # (user_id, product_id), pour tirer des avis d'acheteurs
    achats: list[tuple[int, int]] = []

    for user_id, inscrit_le in users:
        # Un peu plus d'un tiers des inscrits commandent
        if rng.random() > 0.36:
            continue

        # La plupart n'achètent qu'une fois, une minorité revient souvent
        nombre = rng.choices([1, 2, 3, 4, 6], weights=[64, 20, 9, 5, 2], k=1)[0]

        for _ in range(nombre):
            passee_le = _recent_biased(rng, inscrit_le, now, courbure=1.0)
            indice = len(commandes)

            # 1 à 3 références : la première pondérée par la demande, les suivantes
            # surtout dans le même ensemble d'affinité
            k = rng.choices([1, 2, 3], weights=[58, 30, 12], k=1)[0]
            choisis: list[models.Product] = [
                rng.choices(produits, weights=poids_achat, k=1)[0]
            ]
            for _ in range(k * 4):
                if len(choisis) == k:
                    break
                groupes = voisins.get(choisis[0].id)
                if groupes and rng.random() < PART_AFFINITE:
                    groupe = rng.choice(groupes)
                    candidat = rng.choice(groupe)
                else:
                    candidat = rng.choices(produits, weights=poids_achat, k=1)[0]
                if candidat not in choisis:
                    choisis.append(candidat)

            sous_total = 0
            for produit in choisis:
                qty = rng.choices([1, 2, 3], weights=[76, 18, 6], k=1)[0]
                sous_total += produit.price_cents * qty
                lignes.append((indice, produit.id, qty))
                achats.append((user_id, produit.id))

            # Remise et port calculés comme `pricing.py`
            remise = 0
            port_offert = False
            code_promo = None
            if promos and rng.random() < 0.18:
                promo = rng.choice(promos)
                if sous_total >= promo.min_subtotal_cents:
                    code_promo = promo.code
                    if promo.kind == "percent":
                        remise = sous_total * (promo.percent or 0) // 100
                    elif promo.kind == "fixed":
                        remise = min(promo.amount_cents or 0, sous_total)
                    else:
                        port_offert = True

            apres = sous_total - remise
            port = (
                0
                if (apres >= FREE_SHIPPING_THRESHOLD_CENTS or port_offert)
                else SHIPPING_CENTS
            )

            numero = "ATL" + str(rng.randint(100000, 999999))
            while numero in numeros:
                numero = "ATL" + str(rng.randint(100000, 999999))
            numeros.add(numero)

            commandes.append({
                "number": numero,
                "user_id": user_id,
                "email": None,  # complete apres coup, voir `ensure_demo_dataset`
                "status": _order_status(rng, passee_le, now),
                "subtotal_cents": sous_total,
                "discount_cents": remise,
                "shipping_cents": port,
                "total_cents": apres + port,
                "promo_code": code_promo,
                "created_at": passee_le,
            })

    return commandes, lignes, achats


def _build_views(
    rng: random.Random,
    users: list[tuple[int, datetime]],
    produits: list[models.Product],
    total: int,
    now: datetime,
) -> list[dict]:
    """Consultations de fiches, selon l'attractivité des produits."""
    debut = now - timedelta(days=HISTORY_MONTHS * 30)
    poids_vue = [POPULARITE.get(p.code, POPULARITE_DEFAUT)[0] for p in produits]
    ids = [p.id for p in produits]

    vus = rng.choices(ids, weights=poids_vue, k=total)
    rows: list[dict] = []
    for product_id in vus:
        # Un peu plus de la moitié des visites viennent d'un compte connecté
        if rng.random() < 0.55:
            user_id, inscrit_le = users[rng.randrange(len(users))]
            vue_le = _recent_biased(rng, inscrit_le, now, courbure=1.0)
        else:
            user_id = None
            vue_le = _recent_biased(rng, debut, now)
        rows.append({"product_id": product_id, "user_id": user_id, "created_at": vue_le})
    return rows


# Textes rangés par note : un avis à une étoile ne dit pas « je recommande ».
# Tournures sans accord de genre, les auteurs étant de tous les prénoms.
# Copie figée dans migrations/versions/e8b2c4d6f1a3_avis_et_accents_de_demonstration.py.
AVIS_PAR_NOTE = {
    5: [
        "Conforme à la description, emballage soigné.",
        "Encore plus beau en vrai que sur la fiche.",
        "Arrivé en deux jours, rien à redire.",
        "Offert pour un anniversaire : gros succès.",
        "Deuxième commande, toujours le même soin.",
        "Les couleurs sont exactement celles des photos.",
        "Solide, bien fini, on sent l'objet qui va durer.",
        "Exactement ce que je cherchais.",
        "Parfait.",
        "Rapport qualité-prix très correct pour une petite série.",
        "Il a trouvé sa place tout de suite dans le salon.",
        "Emballé dans du papier, sans plastique. Objet impeccable.",
        "Je recommande sans hésiter.",
        "Finitions nettes, aucune bavure.",
        "Le deuxième de la maison, le premier est parti en cadeau.",
        "Très bon achat.",
    ],
    4: [
        "Très bien, un peu plus petit qu'imaginé.",
        "Belle finition, livraison un peu longue.",
        "Joli objet, le prix reste un peu élevé.",
        "Conforme, la notice aurait mérité une version française.",
        "Bonne qualité, une rayure légère sous le socle, rien de grave.",
        "Ravissant, le colis a mis cinq jours.",
        "Bon achat, j'aurais aimé plus de choix de couleurs.",
        "Très joli, mais plus fragile qu'il n'y paraît.",
        "Fidèle aux photos, l'expédition a pris quelques jours de plus.",
    ],
    3: [
        "Correct, sans plus pour le prix.",
        "Joli, mais la finition laisse à désirer par endroits.",
        "Livraison longue, objet conforme.",
        "Rendu moins éclatant que sur les photos.",
        "Un peu décevant pour la taille.",
        "Carton abîmé à l'arrivée, l'objet était intact.",
    ],
    2: [
        "Plus petit et plus léger que prévu, un peu décevant.",
        "Finitions approximatives, retour en cours.",
        "Livré avec une semaine de retard, sans nouvelles entre-temps.",
    ],
    1: [
        "Arrivé cassé. Le remboursement a été rapide, c'est le seul point positif.",
        "Ne ressemble pas vraiment aux photos, renvoyé.",
        "Colis égaré dix jours, objet correct mais expérience pénible.",
    ],
}


def _attribuer_textes(rng: random.Random, avis: list[dict]) -> None:
    """Donne un texte à chaque avis, sans répétition à la suite sur une même fiche.

    Parcourt chaque fiche dans l'ordre d'affichage (vérifiés, puis récents) et
    tire dans la réserve de la note, mélangée par fiche : un texte ne revient
    qu'une fois la réserve épuisée.
    """
    par_produit: dict[int, list[dict]] = {}
    for ligne in avis:
        par_produit.setdefault(ligne["product_id"], []).append(ligne)

    for lignes in par_produit.values():
        lignes.sort(key=lambda a: (not a["verified"], -a["created_at"].timestamp()))
        reserves: dict[int, list[str]] = {}
        for ligne in lignes:
            reserve = reserves.get(ligne["rating"])
            if not reserve:
                reserve = list(AVIS_PAR_NOTE[ligne["rating"]])
                rng.shuffle(reserve)
                reserves[ligne["rating"]] = reserve
            ligne["text"] = reserve.pop()


def _build_reviews(
    rng: random.Random,
    achats: list[tuple[int, int]],
    noms: dict[int, str],
    combien: int,
    now: datetime,
) -> list[dict]:
    """Avis tirés parmi les achats réels du jeu de données."""
    debut = now - timedelta(days=HISTORY_MONTHS * 30)
    vus: set[tuple[int, int]] = set()
    rows: list[dict] = []

    for _ in range(combien * 3):
        if len(rows) >= combien or not achats:
            break
        couple = achats[rng.randrange(len(achats))]
        # Un avis par couple (client, produit)
        if couple in vus:
            continue
        vus.add(couple)
        user_id, product_id = couple
        prenom = noms.get(user_id, "Client").split(" ")[0]
        initiale = noms.get(user_id, "Client X").split(" ")[-1][:1]
        rows.append({
            "product_id": product_id,
            "user_id": user_id,
            "author_name": f"{prenom} {initiale}.",
            # Notes élevées en majorité
            "rating": rng.choices([5, 4, 3, 2, 1], weights=[52, 28, 12, 5, 3], k=1)[0],
            "text": "",
            "verified": True,
            "approved": rng.random() > 0.04,
            "created_at": _recent_biased(rng, debut, now, courbure=1.0),
        })

    _attribuer_textes(rng, rows)
    return rows


def _ajuster_les_stocks(
    rng: random.Random,
    db: Session,
    produits: list[models.Product],
    commandes: list[dict],
    lignes: list[tuple[int, int, int]],
    now: datetime,
) -> None:
    """Recale les stocks sur la vitesse de vente des 90 derniers jours.

    Les stocks du catalogue ne couvrent que quelques heures face à la clientèle
    générée ; trois références restent volontairement sous tension.
    """
    depuis = now - timedelta(days=90)
    recentes: dict[int, int] = {}
    for indice, product_id, qty in lignes:
        if commandes[indice]["created_at"] >= depuis:
            recentes[product_id] = recentes.get(product_id, 0) + qty

    # Tirage déterministe des références sous tension
    sous_tension = set(rng.sample([p.id for p in produits], k=min(3, len(produits))))

    for produit in produits:
        par_jour = recentes.get(produit.id, 0) / 90
        if par_jour <= 0:
            # Référence immobile : stock d'origine conservé
            continue
        couverture = rng.randint(6, 16) if produit.id in sous_tension else rng.randint(35, 90)
        produit.stock = max(1, round(par_jour * couverture))

    db.commit()


# --- Point d'entrée ---
def ensure_demo_dataset(db: Session) -> None:
    """Génère le jeu de démonstration s'il manque des comptes. Idempotente, appelée au démarrage."""
    cible = settings.DEMO_USERS
    if cible <= 0:
        return

    existants = db.execute(select(func.count(models.User.id))).scalar() or 0
    if existants >= cible:
        return

    produits = list(db.scalars(select(models.Product).order_by(models.Product.id)))
    if not produits:
        # Sans catalogue (`seed`), rien à générer
        log.warning("Catalogue vide : jeu de données de démonstration ignoré.")
        return

    a_creer = cible - existants
    rng = random.Random(RANDOM_SEED)
    now = datetime.now(timezone.utc)
    log.warning("Génération du jeu de données de démonstration : %s comptes", a_creer)

    # --- Comptes ---
    deja_pris = set(db.scalars(select(models.User.email)))
    lignes_users = _build_users(rng, a_creer, now, deja_pris)
    dernier_id = db.execute(select(func.coalesce(func.max(models.User.id), 0))).scalar() or 0
    _bulk(db, models.User, lignes_users)

    # Identifiants relus dans l'ordre d'insertion (seul écrivain au démarrage)
    nouveaux = db.execute(
        select(models.User.id).where(models.User.id > dernier_id).order_by(models.User.id)
    ).scalars().all()
    users = [(uid, ligne["created_at"]) for uid, ligne in zip(nouveaux, lignes_users)]
    emails = {uid: ligne["email"] for uid, ligne in zip(nouveaux, lignes_users)}
    noms = {uid: ligne["name"] for uid, ligne in zip(nouveaux, lignes_users)}

    # --- Commandes ---
    promos = list(db.scalars(select(models.Promo).where(models.Promo.active.is_(True))))
    commandes, lignes_brutes, achats = _build_orders(rng, users, produits, promos, now)
    for ligne in commandes:
        ligne["email"] = emails[ligne["user_id"]]

    premier_order = db.execute(select(func.coalesce(func.max(models.Order.id), 0))).scalar() or 0
    _bulk(db, models.Order, commandes)
    ids_commandes = db.execute(
        select(models.Order.id).where(models.Order.id > premier_order).order_by(models.Order.id)
    ).scalars().all()

    par_id = {p.id: p for p in produits}
    lignes_commande = []
    for indice, product_id, qty in lignes_brutes:
        produit = par_id[product_id]
        lignes_commande.append({
            "order_id": ids_commandes[indice],
            "product_id": product_id,
            # Nom et prix figés à la commande
            "name": produit.name,
            "art": produit.art,
            "unit_price_cents": produit.price_cents,
            "unit_cost_cents": produit.cost_cents,
            "qty": qty,
        })
    _bulk(db, models.OrderItem, lignes_commande)

    # --- Audience ---
    total_vues = a_creer * max(0, settings.DEMO_VIEWS_PER_USER)
    if total_vues:
        _bulk(db, models.ProductView, _build_views(rng, users, produits, total_vues, now))

    # --- Avis ---
    avis = _build_reviews(rng, achats, noms, combien=min(700, len(achats) // 4), now=now)
    if avis:
        _bulk(db, models.Review, avis)

    _ajuster_les_stocks(rng, db, produits, commandes, lignes_brutes, now)

    db.commit()
    log.warning(
        "Jeu de donnees pret : %s comptes, %s commandes, %s lignes, %s vues, %s avis.",
        len(lignes_users), len(commandes), len(lignes_commande), total_vues, len(avis),
    )
