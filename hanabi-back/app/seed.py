# -*- coding: utf-8 -*-
"""Données de démarrage : catalogue, codes promo, avis, comptes de démonstration."""
import json
import logging

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .passwords import validate_password
from .security import hash_password

log = logging.getLogger("hanabi.seed")

# Compte client de démonstration, affiché à la connexion
DEMO_EMAIL = "demo@hanabi.fr"

# Compte back-office de démonstration. Identifiants publics, affichés à la
# connexion : les mettre en variable d'environnement ne les rendrait pas secrets.
# Le garde-fou est la lecture seule (`DEMO_ADMIN_READONLY`, voir deps.py).
DEMO_ADMIN_EMAIL = "hanabi@atelier.fr"
DEMO_ADMIN_PASSWORD = "hanabi-logs2026"

# code, nom, catégorie, accroche, prix, stock, nouveau, blason "forme,tracé,fond"
# Blasons dessinés dans ProductArt.jsx, aux couleurs de la charte.
PRODUCTS = [
    ("HNB-014", "Collier Maneki-neko", "Compagnons", "Collier chat, grelot laiton, cuir souple",     2400, 12, False, "suzu,#E0452A,#0A0605"),
    ("HNB-021", "Lampe Torii LED",     "Collection", "Veilleuse torii, USB, trois intensités",        6400, 5,  True,  "torii,#E0452A,#0A0605"),
    ("HNB-008", "Bandana Sushi",       "Compagnons", "Bandana chien, coton, taille réglable",         1800, 25, False, "bandana,#0A0605,#D8452B"),
    ("HNB-015", "Gamelle Sakura",      "Compagnons", "Gamelle céramique, motif fleur de cerisier",    3200, 9,  False, "sakura,#E0452A,#EFE7D6"),
    ("HNB-033", "Baguettes Laquées",   "Tradition",  "Paire, laque urushi, repose-baguettes inclus",  2200, 40, False, "baguettes,#E0452A,#0A0605"),
    ("HNB-037", "Éventail Sensu",      "Tradition",  "Éventail pliant, bambou et papier washi",       2800, 18, True,  "fan,#0A0605,#D8452B"),
    ("HNB-041", "Bol à Ramen",         "Tradition",  "Céramique 1 L, motif vague seigaiha",           2600, 22, False, "bol,#0A0605,#D8452B"),
    ("HNB-009", "Coussin Futon Néko",  "Compagnons", "Couchage chat, futon coton matelassé",          5800, 6,  False, "futon,#0A0605,#EFE7D6"),
    ("HNB-052", "Figurine Kitsune",    "Collection", "Renard en résine, peinte main, 18 cm",          4800, 4,  True,  "kitsune,#E0452A,#0A0605"),
    ("HNB-045", "Tenugui Seigaiha",    "Tradition",  "Serviette coton, teinture traditionnelle",      1600, 50, False, "seigaiha,#0A0605,#A83019"),
    ("HNB-026", "Lampe Lune",          "Collection", "Lampe lune, 16 couleurs, télécommande",         7200, 7,  False, "moon,#0A0605,#EFE7D6"),
    ("HNB-018", "Maneki-neko Doré",    "Collection", "Chat porte-bonheur, bras motorisé solaire",     3800, 14, False, "neko,#0A0605,#D8452B"),
]

# Coût d'achat unitaire en centimes, volontairement hétérogène : le classement
# par marge ne suit pas celui du chiffre d'affaires.
COUTS = {
    "HNB-021": 2900,  # Lampe Torii : 55 % de marge, plus gros volume
    "HNB-026": 4300,  # Lampe Lune : chère à l'achat, marge faible
    "HNB-052": 2100,  # Figurine Kitsune
    "HNB-014": 900,   # Collier Maneki-neko
    "HNB-037": 1050,  # Éventail Sensu
    "HNB-033": 700,   # Baguettes : meilleure marge du catalogue
    "HNB-041": 1000,  # Bol à Ramen
    "HNB-045": 550,   # Tenugui : petit prix, marge élevée, forte rotation
    "HNB-008": 780,   # Bandana Sushi
    "HNB-015": 1600,  # Gamelle Sakura
    "HNB-018": 2400,  # Maneki-neko Doré : marge la plus faible
    "HNB-009": 3500,  # Coussin Futon : cher, peu vendu, peu rentable
}

def gallery(art: str) -> list[str]:
    """Trois vues du blason : tel quel, matières inversées, gros plan."""
    forme, trace, fond = art.split(",")
    return [art, f"{forme},{fond},{trace}", f"{art},gros-plan"]


PROMOS = [
    ("BIENVENUE10", "percent", 10, None, 0),
    ("DROP5",       "fixed",   None, 500, 3000),
    ("PORTOFFERT",  "free_shipping", None, None, 0),
]

REVIEWS = {
    "HNB-021": [("Yuki M.", 5, "Lumière parfaite pour la chambre, le rouge du torii est superbe la nuit."),
                ("Sofiane B.", 4, "Trois intensités bien pensées, câble un peu court.")],
    "HNB-014": [("Camille R.", 5, "Mon chat le porte sans broncher, le grelot est discret.")],
    "HNB-033": [("Léa F.", 5, "La laque est magnifique, et elles sont bien équilibrées en main."),
                ("Marc D.", 4, "Le repose-baguettes est un vrai plus."),
                ("Inès P.", 5, "Qualité au-dessus du prix.")],
    "HNB-037": [("Théo L.", 5, "Bois solide, papier épais, se déplie sans accroc.")],
    "HNB-041": [("Sarah K.", 5, "Taille généreuse, le motif vague est très net."),
                ("Paul V.", 4, "Passe au lave-vaisselle, RAS.")],
    "HNB-052": [("Nina T.", 5, "Peinture nette, aucune bavure, socle stable.")],
    "HNB-026": [("Adam C.", 5, "Les enfants adorent, la télécommande marche bien."),
                ("Lou R.", 4, "Rendu lune réaliste, batterie correcte.")],
}


def seed(db: Session) -> None:
    if db.query(models.Product).first():
        return

    code_to_id: dict[str, int] = {}
    for code, name, cat, blurb, price, stock, is_new, art in PRODUCTS:
        p = models.Product(code=code, name=name, category=cat, blurb=blurb,
                            price_cents=price, cost_cents=COUTS.get(code, 0),
                            stock=stock, is_new=is_new, art=art,
                            images=json.dumps(gallery(art)))
        db.add(p)
        db.flush()
        code_to_id[code] = p.id

    for code, kind, percent, amount, mini in PROMOS:
        db.add(models.Promo(code=code, kind=kind, percent=percent, amount_cents=amount,
                            min_subtotal_cents=mini, active=True))

    for code, items in REVIEWS.items():
        pid = code_to_id[code]
        for author, rating, text in items:
            db.add(models.Review(product_id=pid, user_id=None, author_name=author,
                                rating=rating, text=text, verified=False, approved=True))

    # Client ordinaire, sans droits d'administration : ses identifiants sont publics
    db.add(models.User(
        name="Souleyman Demo", email=DEMO_EMAIL,
        password_hash=hash_password("demo1234"), is_admin=False,
    ))
    db.commit()


def _demote_public_demo(db: Session) -> None:
    """Retire les droits d'administration au compte client de démonstration.

    Pour les bases antérieures à la séparation des deux comptes. Sans effet si
    ADMIN_EMAIL désigne justement ce compte.
    """
    demo = db.query(models.User).filter(models.User.email == DEMO_EMAIL).first()
    if demo is None or not demo.is_admin:
        return
    if settings.ADMIN_EMAIL.strip().lower() == DEMO_EMAIL:
        return

    demo.is_admin = False
    db.commit()
    log.warning(
        "Droits d'administration retirés à %s : ses identifiants sont publics. "
        "Utilise ADMIN_EMAIL / ADMIN_PASSWORD pour désigner un administrateur.",
        DEMO_EMAIL,
    )


def ensure_public_admin(db: Session) -> None:
    """Crée ou remet à niveau le compte back-office de démonstration, à chaque démarrage.

    Le mot de passe est réappliqué pour suivre la constante. `validate_password`
    n'est pas appelée : ce mot de passe public reprend l'adresse, ce qu'elle refuserait.
    """
    if not settings.PUBLIC_ADMIN_DEMO:
        return

    compte = db.query(models.User).filter(models.User.email == DEMO_ADMIN_EMAIL).first()
    if compte is None:
        db.add(models.User(
            name="Back-office (démonstration)",
            email=DEMO_ADMIN_EMAIL,
            password_hash=hash_password(DEMO_ADMIN_PASSWORD),
            is_admin=True,
        ))
        db.commit()
        log.warning(
            "Compte back-office de démonstration créé : %s (lecture seule : %s)",
            DEMO_ADMIN_EMAIL, settings.DEMO_ADMIN_READONLY,
        )
        return

    compte.is_admin = True
    compte.password_hash = hash_password(DEMO_ADMIN_PASSWORD)
    db.commit()


def ensure_admin(db: Session) -> None:
    """Crée ou promeut l'administrateur décrit par l'environnement. Idempotente.

    Sans ADMIN_EMAIL ni ADMIN_PASSWORD, aucun administrateur n'est créé.
    """
    _demote_public_demo(db)

    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        log.info(
            "Aucun administrateur provisionné (ADMIN_EMAIL / ADMIN_PASSWORD absents). "
            "Le back-office restera inaccessible."
        )
        return

    email = settings.ADMIN_EMAIL.strip().lower()

    problem = validate_password(settings.ADMIN_PASSWORD, email=email)
    if problem:
        log.error("ADMIN_PASSWORD refusé : %s Aucun administrateur créé.", problem)
        return

    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        if not existing.is_admin:
            existing.is_admin = True
            db.commit()
            log.warning("Compte existant promu administrateur : %s", email)
        return

    db.add(models.User(
        name="Administration",
        email=email,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        is_admin=True,
    ))
    db.commit()
    log.warning("Compte administrateur créé : %s", email)
