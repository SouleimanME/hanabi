# -*- coding: utf-8 -*-
"""Population fictive, pour que le tableau de bord ait quelque chose a montrer.

Le back-office de ce projet sert a demontrer une chaine decisionnelle complete :
audience, conversion, panier moyen, rotation du catalogue. Sur une base vide,
aucun de ces indicateurs ne veut rien dire - un taux de conversion calcule sur
deux commandes n'est pas un taux de conversion, c'est un accident. On genere
donc une clientele, son historique d'achat et son audience.

Trois exigences ont guide l'ecriture :

1. **Deterministe.** Le tirage part d'une graine fixe, si bien que deux
   installations affichent les memes chiffres. Une capture d'ecran du tableau de
   bord reste donc valable, et une regression de calcul se voit immediatement.

2. **Rapide.** Le plan gratuit de l'hebergeur reconstruit la base a chaque
   redemarrage : la generation se joue pendant le demarrage du service, et doit
   donc se compter en secondes. D'ou les insertions par lots et, surtout, le
   condensat de mot de passe calcule une seule fois - bcrypt coute environ
   0,3 s par appel, ce qui ferait pres d'une heure sur dix mille comptes.

3. **Coherente.** Les chiffres doivent se tenir entre eux : une commande est
   posterieure a l'inscription de son auteur, un article beaucoup vu et peu
   achete l'est pour une raison lisible (son prix), les totaux respectent la
   regle de port offert appliquee par `pricing.py`. Un jeu de donnees
   uniformement aleatoire produit des graphiques plats et des correlations
   nulles, c'est-a-dire exactement ce qu'aucune boutique ne connait.

Les comptes generes portent tous le meme mot de passe, sans interet puisqu'ils
ne servent jamais a se connecter : ce sont des lignes de base de donnees, pas
des acces. Leurs adresses sont fictives et construites sur des domaines
grand public afin que la repartition ressemble a celle d'une vraie clientele.
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

# Graine du tirage. Toute modification rebat l'ensemble des chiffres.
RANDOM_SEED = 20260731

# Profondeur de l'historique genere.
HISTORY_MONTHS = 24

# Mot de passe commun aux comptes fictifs. Ils ne sont pas destines a servir :
# aucun n'est administrateur et aucun n'est affiche nulle part.
FILLER_PASSWORD = "hanabi-demo-population-2026"

# Nombre maximal de parametres lies par instruction.
#
# PostgreSQL en accepte 65535, SQLite 32766 depuis la version 3.32. On retient
# la borne la plus basse : elle vaut pour les deux, et rien ne justifie de
# s'approcher du plafond.
MAX_PARAMS = 30_000

# Plafond de lignes par instruction, independamment du nombre de colonnes. Une
# requete de plusieurs mega-octets ne gagne plus rien et consomme de la memoire
# des deux cotes.
MAX_ROWS = 5_000


# ------------------------------------------------------------------ #
# Vocabulaire                                                         #
# ------------------------------------------------------------------ #
PRENOMS_M = [
    "Lucas", "Hugo", "Nathan", "Enzo", "Louis", "Gabriel", "Jules", "Arthur",
    "Raphael", "Leo", "Adam", "Mael", "Paul", "Noah", "Ethan", "Tom", "Theo",
    "Sacha", "Antoine", "Baptiste", "Clement", "Maxime", "Nicolas", "Julien",
    "Thomas", "Alexandre", "Pierre", "Romain", "Quentin", "Florian", "Mehdi",
    "Yanis", "Samir", "Karim", "Bastien", "Victor", "Simon", "Mathis", "Axel",
    "Gaspard", "Come", "Timothee", "Ilyes", "Rayan", "Souleymane", "Amine",
]
PRENOMS_F = [
    "Emma", "Jade", "Louise", "Alice", "Chloe", "Lina", "Rose", "Lea", "Manon",
    "Camille", "Sarah", "Ines", "Anna", "Julie", "Marie", "Clara", "Zoe", "Eva",
    "Lucie", "Charlotte", "Mathilde", "Oceane", "Pauline", "Laura", "Elise",
    "Amandine", "Nina", "Margaux", "Claire", "Sofia", "Yasmine", "Aya",
    "Maelys", "Juliette", "Agathe", "Romane", "Solene", "Lou", "Ambre", "Celia",
    "Nour", "Fatoumata", "Salome", "Anais", "Justine",
]
# Prenoms epicenes, reserves aux comptes sans civilite affirmee.
PRENOMS_N = ["Camille", "Alix", "Charlie", "Sasha", "Andrea", "Noa", "Swann", "Maxence"]

NOMS = [
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit",
    "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel",
    "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier", "Morel",
    "Girard", "Andre", "Lefevre", "Mercier", "Dupont", "Lambert", "Bonnet",
    "Francois", "Martinez", "Legrand", "Garnier", "Faure", "Rousseau", "Blanc",
    "Guerin", "Muller", "Henry", "Roussel", "Nicolas", "Perrin", "Morin",
    "Mathieu", "Clement", "Gauthier", "Dumont", "Lopez", "Fontaine",
    "Chevalier", "Robin", "Masson", "Sanchez", "Gerard", "Nguyen", "Boyer",
    "Denis", "Lemaire", "Duval", "Joly", "Gautier", "Roger", "Roche", "Roy",
    "Noel", "Meyer", "Lucas", "Meunier", "Jean", "Perez", "Marchand", "Dufour",
    "Blanchard", "Barbier", "Brun", "Dumas", "Brunet", "Schmitt", "Leroux",
    "Colin", "Fernandez", "Renard", "Arnaud", "Rolland", "Caron", "Aubert",
    "Giraud", "Leclerc", "Vidal", "Bourgeois", "Renaud", "Lemoine", "Picard",
    "Gaillard", "Philippe", "Leclercq", "Lacroix", "Fabre", "Dupuis",
    "Traore", "Diallo", "Benali", "Cohen", "Da Silva", "Ferreira",
]

# (ville, code postal, poids). Les poids suivent grossierement la population des
# aires urbaines : sans cela, le graphique « top villes » sort douze barres de
# meme hauteur, ce qui n'apprend rien.
VILLES = [
    ("Paris", "75011", 100), ("Marseille", "13006", 34), ("Lyon", "69003", 32),
    ("Toulouse", "31000", 26), ("Nice", "06000", 18), ("Nantes", "44000", 20),
    ("Montpellier", "34000", 17), ("Strasbourg", "67000", 16),
    ("Bordeaux", "33000", 21), ("Lille", "59000", 19), ("Rennes", "35000", 15),
    ("Reims", "51100", 10), ("Toulon", "83000", 9), ("Grenoble", "38000", 13),
    ("Dijon", "21000", 9), ("Angers", "49000", 9), ("Nimes", "30000", 8),
    ("Villeurbanne", "69100", 8), ("Clermont-Ferrand", "63000", 8),
    ("Le Mans", "72000", 7), ("Aix-en-Provence", "13100", 8),
    ("Brest", "29200", 7), ("Tours", "37000", 7), ("Amiens", "80000", 6),
    ("Limoges", "87000", 6), ("Annecy", "74000", 6), ("Perpignan", "66000", 6),
    ("Besancon", "25000", 6), ("Metz", "57000", 6), ("Rouen", "76000", 7),
    ("Orleans", "45000", 6), ("Mulhouse", "68100", 5), ("Caen", "14000", 6),
    ("Nancy", "54000", 6), ("Argenteuil", "95100", 5), ("Roubaix", "59100", 5),
    ("Avignon", "84000", 5), ("La Rochelle", "17000", 5), ("Pau", "64000", 4),
    ("Bayonne", "64100", 4), ("Colmar", "68000", 4), ("Quimper", "29000", 4),
    ("Chambery", "73000", 4), ("Biarritz", "64200", 3), ("Vannes", "56000", 3),
]

CODES_POSTAUX = {ville: cp for ville, cp, _ in VILLES}

RUES = [
    "rue des Lilas", "avenue Jean Jaures", "rue de la Republique",
    "boulevard Victor Hugo", "rue Pasteur", "allee des Peupliers",
    "rue Gambetta", "avenue de la Gare", "rue du Moulin", "impasse des Rosiers",
    "rue Emile Zola", "cours Lafayette", "rue Saint-Martin", "quai des Chartrons",
    "rue de la Paix", "chemin des Vignes", "place du Marche", "rue Voltaire",
    "avenue Foch", "rue des Ecoles", "rue Berthelot", "rue Carnot",
]

COMPLEMENTS = ["Bat. A", "Bat. B", "Appt 12", "Appt 3B", "2e etage", "Residence Les Tilleuls"]

# Parts de marche approximatives des messageries en France. Determine a quoi
# ressemble la colonne e-mail du back-office.
DOMAINES = [
    ("gmail.com", 42), ("orange.fr", 13), ("hotmail.fr", 9), ("outlook.fr", 8),
    ("free.fr", 7), ("yahoo.fr", 6), ("laposte.net", 5), ("sfr.fr", 4),
    ("wanadoo.fr", 3), ("icloud.com", 2), ("protonmail.com", 1),
]

# Poids d'audience et poids d'achat, par code produit.
#
# Les deux series sont volontairement decorrelees : c'est l'ecart entre elles
# qui rend le tableau de bord interessant. Une lampe a 72 euros se regarde
# beaucoup et s'achete peu ; un tenugui a 16 euros se regarde moins et se
# transforme bien. Un jeu de donnees ou les deux colonnes seraient identiques
# afficherait un taux de conversion constant, donc aucune decision a prendre.
POPULARITE = {
    # code       vues  achats
    "HNB-021": (100, 78),   # Lampe Torii : la vedette, forte sur les deux axes
    "HNB-026": (88, 21),    # Lampe Lune : tres regardee, chere, convertit mal
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

# Ensembles d'articles qui se commandent ensemble.
#
# Sans eux, le generateur tire chaque ligne d'une commande independamment des
# autres, et l'analyse de panier ne trouve rien : toutes les paires ressortent
# avec un lift legerement inferieur a 1, signature exacte d'un tirage sans
# remise entre evenements independants. Autrement dit, la vue affinites
# fonctionnerait parfaitement et n'aurait rien a montrer.
#
# Les regroupements ci-dessous imitent des intentions d'achat reelles - dresser
# une table, equiper un animal, composer une ambiance - plutot que les
# categories du catalogue. Le dernier les traverse volontairement : une regle
# d'association qui ne ferait que redecouvrir les categories n'apprendrait rien
# a personne.
AFFINITES = [
    ["HNB-033", "HNB-041", "HNB-045"],            # le repas
    ["HNB-014", "HNB-008", "HNB-015", "HNB-009"],  # le compagnon
    ["HNB-021", "HNB-026", "HNB-052", "HNB-018"],  # l'ambiance
    ["HNB-037", "HNB-021", "HNB-045"],             # le cadeau, toutes categories
]

# Part des articles complementaires tires dans le meme ensemble d'affinite. Le
# reste des lignes est tire dans tout le catalogue : une commande sur trois
# environ melange des univers, ce qui evite des regles trop parfaites pour etre
# credibles.
PART_AFFINITE = 0.62


# ------------------------------------------------------------------ #
# Outils de tirage                                                    #
# ------------------------------------------------------------------ #
def _slug(value: str) -> str:
    """Reduit un prenom ou un nom a ce qui peut figurer dans une adresse."""
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return plain.lower().replace(" ", "-").replace("'", "")


def _weighted(rng: random.Random, items: list[tuple], count: int) -> list:
    """Tire `count` elements parmi des couples (valeur, poids)."""
    values = [it[0] for it in items]
    weights = [it[-1] for it in items]
    return rng.choices(values, weights=weights, k=count)


def _recent_biased(
    rng: random.Random, start: datetime, end: datetime, courbure: float = 2.0
) -> datetime:
    """Date tiree entre deux bornes, avec un biais vers la fin de la periode.

    Une boutique qui fonctionne recrute davantage de clients ce mois-ci que
    vingt-quatre mois plus tot. Elever un tirage uniforme a une puissance
    concentre les dates vers `end` et donne une courbe de croissance, la ou un
    tirage plat produirait un histogramme parfaitement horizontal - lisible,
    mais faux.

    `courbure` vaut 1 pour un tirage uniforme. Les dates de commande s'en
    servent : elles heritent deja de la croissance par la date d'inscription de
    leur auteur, et rajouter un biais par-dessus multipliait les deux effets.
    Le dernier mois ressortait alors a plus du double du precedent - une courbe
    en crosse de hockey qu'aucune boutique ne connait, et qui aurait rendu tout
    le reste du graphique illisible.
    """
    span = (end - start).total_seconds()
    if span <= 0:
        return end
    # 1 - (1-u)^k : densite croissante, sans discontinuite.
    u = rng.random()
    position = 1 - (1 - u) ** courbure
    # Saisonnalite : un creux en ete, un pic avant les fetes.
    moment = start + timedelta(seconds=span * position)
    if moment.month in (7, 8) and rng.random() < 0.35:
        moment -= timedelta(days=rng.randint(60, 120))
    elif moment.month in (11, 12) and rng.random() < 0.20:
        moment += timedelta(days=rng.randint(0, 20))
    return min(max(moment, start), end)


def _birthdate(rng: random.Random) -> str:
    """Date de naissance, avec une pyramide des ages plausible.

    Les tranches suivent une clientele de boutique en ligne d'objets deco :
    coeur de cible entre 25 et 44 ans, extremites plus rares.
    """
    tranche = rng.choices(
        [(16, 17), (18, 24), (25, 34), (35, 44), (45, 54), (55, 72)],
        weights=[2, 17, 34, 25, 14, 8],
        k=1,
    )[0]
    age = rng.randint(*tranche)
    today = datetime.now(timezone.utc).date()
    # On retire l'age en jours plutot qu'en annees pour repartir les
    # anniversaires sur toute l'annee.
    naissance = today - timedelta(days=age * 365 + rng.randint(0, 364))
    return naissance.isoformat()


# ------------------------------------------------------------------ #
# Generation                                                          #
# ------------------------------------------------------------------ #
def _bulk(db: Session, model, rows: list[dict]) -> None:
    """Insere une liste de dictionnaires en un minimum d'allers-retours.

    Le point important est `.values(lot)` plutot que la forme
    `db.execute(insert(model), lot)`. La seconde parait equivalente et se
    comporte tres differemment : elle passe par `executemany`, qui emet une
    instruction par ligne. Sur SQLite, ou l'aller-retour est gratuit, la
    difference ne se voit pas. Sur une base distante, dix mille lignes
    deviennent dix mille allers-retours : la generation, immediate en local,
    ne se terminait plus.

    `.values(lot)` construit une seule instruction `INSERT ... VALUES (...),
    (...), ...`, donc un aller-retour par lot. La taille du lot est bornee par
    le nombre de parametres que le moteur accepte, d'ou le calcul a partir du
    nombre de colonnes.
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
        # Repartition volontairement inegale et incomplete : une base reelle
        # comporte toujours une part de champs non renseignes, et le tableau de
        # bord doit savoir l'afficher plutot que de la masquer.
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
        # Les homonymes existent : on ne les evite pas, on les numerote, comme
        # le ferait un formulaire d'inscription refusant une adresse deja prise.
        if adresse in taken:
            adresse = f"{base}{rng.randint(2, 99)}.{i}@{domaines[i]}"
        taken.add(adresse)

        rows.append({
            "name": f"{prenom} {nom}",
            "email": adresse,
            "password_hash": mot_de_passe,
            "civility": civilite,
            # Un cinquieme des comptes n'a pas renseigne sa date de naissance.
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
    """Statut coherent avec l'anciennete de la commande.

    Une commande d'il y a un an est livree ; une commande d'hier est encore en
    preparation. Tirer le statut independamment de la date produirait des
    commandes « expediees » vieilles de dix-huit mois, ce qui saute aux yeux
    dans la liste du back-office.
    """
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
    """Construit les commandes et leurs lignes.

    Renvoie les lignes de commande sous une forme intermediaire : la cle
    etrangere `order_id` n'est connue qu'apres insertion des commandes, on
    conserve donc l'indice de la commande et on le resout ensuite.
    """
    poids_achat = [POPULARITE.get(p.code, POPULARITE_DEFAUT)[1] for p in produits]
    numeros: set[str] = set()

    # Ensembles d'affinite resolus en produits, indexes par produit meneur.
    par_code = {p.code: p for p in produits}
    voisins: dict[int, list[list[models.Product]]] = {}
    for groupe in AFFINITES:
        membres = [par_code[c] for c in groupe if c in par_code]
        for membre in membres:
            voisins.setdefault(membre.id, []).append(membres)

    commandes: list[dict] = []
    # (indice de commande, product_id, qty) - order_id resolu apres insertion.
    lignes: list[tuple[int, int, int]] = []
    # (user_id, product_id) : sert ensuite a tirer des avis d'acheteurs reels.
    achats: list[tuple[int, int]] = []

    for user_id, inscrit_le in users:
        # Un peu plus d'un tiers des inscrits passent commande. Le reste a cree
        # un compte sans jamais acheter - c'est le cas majoritaire en ligne, et
        # l'ignorer donnerait un taux de conversion irrealiste.
        if rng.random() > 0.36:
            continue

        # Distribution de fidelite : la plupart n'achetent qu'une fois, une
        # minorite revient souvent. C'est ce qui rend le taux de reachat et le
        # classement des meilleurs clients lisibles.
        nombre = rng.choices([1, 2, 3, 4, 6], weights=[64, 20, 9, 5, 2], k=1)[0]

        for _ in range(nombre):
            passee_le = _recent_biased(rng, inscrit_le, now, courbure=1.0)
            indice = len(commandes)

            # 1 a 3 references distinctes. Le premier article est tire dans tout
            # le catalogue, pondere par la demande ; les suivants proviennent le
            # plus souvent du meme ensemble d'affinite, comme dans un vrai
            # panier ou l'on complete une intention plutot qu'on ne pioche au
            # hasard.
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

            # Remise et port : on rejoue exactement les regles de `pricing.py`,
            # sinon les totaux affiches par le back-office ne correspondraient
            # pas a ce que le site facture aujourd'hui.
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
    """Consultations de fiches, reparties selon l'attractivite des produits."""
    debut = now - timedelta(days=HISTORY_MONTHS * 30)
    poids_vue = [POPULARITE.get(p.code, POPULARITE_DEFAUT)[0] for p in produits]
    ids = [p.id for p in produits]

    vus = rng.choices(ids, weights=poids_vue, k=total)
    rows: list[dict] = []
    for product_id in vus:
        # Un peu plus de la moitie des visites sont le fait d'un compte
        # identifie ; le reste navigue sans etre connecte, et la ligne reste
        # alors anonyme.
        if rng.random() < 0.55:
            user_id, inscrit_le = users[rng.randrange(len(users))]
            vue_le = _recent_biased(rng, inscrit_le, now, courbure=1.0)
        else:
            user_id = None
            vue_le = _recent_biased(rng, debut, now)
        rows.append({"product_id": product_id, "user_id": user_id, "created_at": vue_le})
    return rows


AVIS_TEXTES = [
    "Conforme a la description, emballage soigne.",
    "Tres belle piece, encore plus jolie en vrai.",
    "Livraison rapide, rien a redire.",
    "Bon rapport qualite-prix, je recommande.",
    "Finitions correctes, sans plus pour le prix.",
    "Exactement ce que je cherchais, merci.",
    "Cadeau qui a fait son effet.",
    "Un peu plus petit qu'imagine, mais la qualite est la.",
    "Deuxieme commande, toujours aussi satisfait.",
    "Le rendu des couleurs est fidele aux photos.",
    "Solide et bien pense, rien a signaler.",
    "Correct, mais l'envoi a mis du temps.",
]


def _build_reviews(
    rng: random.Random,
    achats: list[tuple[int, int]],
    noms: dict[int, str],
    combien: int,
    now: datetime,
) -> list[dict]:
    """Avis rediges par de vrais acheteurs du jeu de donnees.

    Tires parmi les achats effectues, et non au hasard dans le catalogue : un
    avis « achat verifie » sur un produit jamais commande par son auteur serait
    incoherent des qu'on croise les deux tables.
    """
    debut = now - timedelta(days=HISTORY_MONTHS * 30)
    vus: set[tuple[int, int]] = set()
    rows: list[dict] = []

    for _ in range(combien * 3):
        if len(rows) >= combien or not achats:
            break
        couple = achats[rng.randrange(len(achats))]
        # La table impose un avis unique par couple (client, produit).
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
            # Notes elevees en majorite, comme sur toute place de marche.
            "rating": rng.choices([5, 4, 3, 2, 1], weights=[52, 28, 12, 5, 3], k=1)[0],
            "text": rng.choice(AVIS_TEXTES),
            "verified": True,
            "approved": rng.random() > 0.04,
            "created_at": _recent_biased(rng, debut, now, courbure=1.0),
        })

    return rows


def _ajuster_les_stocks(
    rng: random.Random,
    db: Session,
    produits: list[models.Product],
    commandes: list[dict],
    lignes: list[tuple[int, int, int]],
    now: datetime,
) -> None:
    """Recale les stocks sur le rythme de vente reellement genere.

    Le catalogue de depart porte des stocks de petite boutique - cinq lampes,
    quarante paires de baguettes. Rapportes a la clientele generee, ils
    representent quelques heures de vente : la couverture de stock affichait
    alors zero jour pour les douze references, et l'alerte de rupture, en
    signalant tout, ne signalait plus rien.

    On repart donc de la vitesse d'ecoulement observee sur les quatre-vingt-dix
    derniers jours et on vise une couverture plausible. Trois references sont
    volontairement laissees sous tension : une alerte qui ne se declenche jamais
    ne demontre pas davantage qu'une alerte permanente.
    """
    depuis = now - timedelta(days=90)
    recentes: dict[int, int] = {}
    for indice, product_id, qty in lignes:
        if commandes[indice]["created_at"] >= depuis:
            recentes[product_id] = recentes.get(product_id, 0) + qty

    # Les references sous tension sont tirees une fois pour toutes, de facon
    # deterministe comme le reste du jeu de donnees.
    sous_tension = set(rng.sample([p.id for p in produits], k=min(3, len(produits))))

    for produit in produits:
        par_jour = recentes.get(produit.id, 0) / 90
        if par_jour <= 0:
            # Reference qui ne s'ecoule plus : on lui laisse son stock d'origine,
            # c'est precisement le cas du fond de catalogue immobilise.
            continue
        couverture = rng.randint(6, 16) if produit.id in sous_tension else rng.randint(35, 90)
        produit.stock = max(1, round(par_jour * couverture))

    db.commit()


# ------------------------------------------------------------------ #
# Point d'entree                                                      #
# ------------------------------------------------------------------ #
def ensure_demo_dataset(db: Session) -> None:
    """Genere la population fictive si elle n'est pas deja la.

    Idempotente et appelee a chaque demarrage, comme `ensure_admin` : la base de
    l'hebergement gratuit est reconstruite a chaque redeploiement, et un jeu de
    donnees qui ne serait insere qu'a la creation du catalogue disparaitrait au
    premier redemarrage.
    """
    cible = settings.DEMO_USERS
    if cible <= 0:
        return

    existants = db.execute(select(func.count(models.User.id))).scalar() or 0
    if existants >= cible:
        return

    produits = list(db.scalars(select(models.Product).order_by(models.Product.id)))
    if not produits:
        # Le catalogue est pose par `seed`. Sans lui, ni commande ni vue n'ont
        # de sens : on preferera ne rien generer plutot qu'une base bancale.
        log.warning("Catalogue vide : jeu de donnees de demonstration ignore.")
        return

    a_creer = cible - existants
    rng = random.Random(RANDOM_SEED)
    now = datetime.now(timezone.utc)
    log.warning("Generation du jeu de donnees de demonstration : %s comptes...", a_creer)

    # --- Comptes ---
    deja_pris = set(db.scalars(select(models.User.email)))
    lignes_users = _build_users(rng, a_creer, now, deja_pris)
    dernier_id = db.execute(select(func.coalesce(func.max(models.User.id), 0))).scalar() or 0
    _bulk(db, models.User, lignes_users)

    # Les identifiants ne sont pas renvoyes par une insertion par lots. On les
    # relit dans l'ordre d'insertion, ce qui les reapparie a coup sur avec les
    # dictionnaires ci-dessus - le demarrage est le seul ecrivain a cet instant.
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
            # Nom et prix figes au moment de la commande, comme le fait le
            # parcours d'achat reel.
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
