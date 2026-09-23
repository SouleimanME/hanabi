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

# Photos Unsplash (licence libre, usage commercial), servies recadrées au carré
# par leur CDN. Chacune a été regardée en grand avant d'être retenue ; auteurs
# et pages sources dans CREDITS_PHOTOS.
_U = "https://images.unsplash.com/"
_CARRE = "?w=1200&h=1200&q=80&auto=format&fit=crop"
PHOTOS = {
    "HNB-052": _U + "photo-1615961482046-1645fd0c9920" + _CARRE,
    "HNB-018": _U + "photo-1630929927781-cf12ebc522d6" + _CARRE + "&crop=focalpoint&fp-x=0.5&fp-y=0.36&fp-z=1",
    "HNB-067": _U + "photo-1761296123620-1c756e3f6104" + _CARRE,
    "HNB-071": _U + "photo-1640906631464-cc7bebc39d9f" + _CARRE + "&crop=focalpoint&fp-x=0.45&fp-y=0.5&fp-z=1",
    "HNB-074": _U + "photo-1761501156501-d6e4fd7cde5f" + _CARRE + "&crop=focalpoint&fp-x=0.6&fp-y=0.55&fp-z=1",
    "HNB-037": _U + "photo-1777563878028-7ff03f169216" + _CARRE,
    "HNB-061": _U + "photo-1681632973091-1e2725d00da3" + _CARRE + "&crop=focalpoint&fp-x=0.5&fp-y=0.42&fp-z=1",
    "HNB-064": _U + "photo-1746987443790-79b01cd6a83f" + _CARRE + "&crop=focalpoint&fp-x=0.5&fp-y=0.5&fp-z=1.7",
    "HNB-078": _U + "photo-1783958384742-b316026f543c" + _CARRE + "&crop=focalpoint&fp-x=0.33&fp-y=0.5&fp-z=1",
    "HNB-021": _U + "photo-1538590586149-5fa9291f0de0" + _CARRE,
    "HNB-026": _U + "photo-1632712535563-c30adb9a9e2e" + _CARRE,
    "HNB-083": _U + "photo-1557404756-2896e84ca347" + _CARRE + "&crop=focalpoint&fp-x=0.33&fp-y=0.5&fp-z=1",
}

# code : (auteur, page Unsplash), repris dans les mentions légales
CREDITS_PHOTOS = {
    "HNB-052": ("Susann Schuster", "https://unsplash.com/photos/TrB4UA1rDeQ"),
    "HNB-018": ("Christina Dahl", "https://unsplash.com/photos/qChnG1YtIEQ"),
    "HNB-067": ("Hai Nguyen", "https://unsplash.com/photos/gBrxnwjjzr8"),
    "HNB-071": ("Geoff Oliver", "https://unsplash.com/photos/C9VcRCTdjdM"),
    "HNB-074": ("Guru Ankam", "https://unsplash.com/photos/kWC71Qo-0x4"),
    "HNB-037": ("Smithsonian", "https://unsplash.com/photos/FgVqMnm1IMY"),
    "HNB-061": ("Se. Tsuchiya", "https://unsplash.com/photos/NvgvBXf4Mpw"),
    "HNB-064": ("Tasha Kostyuk", "https://unsplash.com/photos/_eoQ8_ASlvM"),
    "HNB-078": ("The Metropolitan Museum of Art", "https://unsplash.com/photos/ZBH-w0cjl6E"),
    "HNB-021": ("Chandan Chaurasia", "https://unsplash.com/photos/8HfAcN5DdpY"),
    "HNB-026": ("Kristine Wook", "https://unsplash.com/photos/j9iRNNL7W5A"),
    "HNB-083": ("Nanxin Zhao", "https://unsplash.com/photos/1crJ5KxPw5s"),
}

# code, nom, catégorie, accroche, prix, stock, nouveau
# Figurines et décoration venues des yokai, des estampes et des animés, sans
# personnage sous licence.
PRODUCTS = [
    ("HNB-052", "Figurine Kitsune",     "Figurines",  "Renard en résine, peinte main, 18 cm",                 4800, 4,  False),
    ("HNB-018", "Maneki-neko Doré",     "Figurines",  "Chat porte-bonheur, bras motorisé solaire",            3800, 14, False),
    ("HNB-067", "Daruma Rouge",         "Figurines",  "Papier mâché, yeux à peindre, 12 cm",                  2400, 30, False),
    ("HNB-071", "Kokeshi Hana",         "Figurines",  "Bois tourné, fleurs peintes main, 10 cm",              3400, 12, False),
    ("HNB-074", "Figurine Ryū",         "Figurines",  "Dragon en résine laquée, perle de cristal, 15 cm",     5600, 6,  True),
    ("HNB-037", "Éventail Sensu",       "Décoration", "Bambou et papier washi, support mural inclus",         2800, 18, False),
    ("HNB-061", "Masque Kitsune",       "Décoration", "Résine peinte main, cordon de soie, à suspendre",      3900, 10, True),
    ("HNB-064", "Masque Hannya",        "Décoration", "Masque mural en résine, cornes dorées, 22 cm",         6200, 5,  False),
    ("HNB-078", "Estampe Grande Vague", "Décoration", "D'après Hokusai, impression sur papier washi, 30 × 40 cm", 4500, 20, False),
    ("HNB-021", "Lampe Torii LED",      "Luminaires", "Veilleuse torii, USB, trois intensités",               6400, 5,  True),
    ("HNB-026", "Lampe Lune",           "Luminaires", "Lampe lune, 16 couleurs, télécommande",                7200, 7,  False),
    ("HNB-083", "Lanterne Ramen",       "Luminaires", "Chōchin en papier et bambou, LED chaude, 45 cm",       4200, 9,  False),
]

# Coût d'achat unitaire en centimes, volontairement hétérogène : le classement
# par marge ne suit pas celui du chiffre d'affaires.
COUTS = {
    "HNB-021": 2900,  # Lampe Torii : 55 % de marge, plus gros volume
    "HNB-026": 4300,  # Lampe Lune : chère à l'achat, marge faible
    "HNB-052": 2100,  # Figurine Kitsune
    "HNB-061": 1400,  # Masque Kitsune
    "HNB-037": 1050,  # Éventail Sensu
    "HNB-067": 700,   # Daruma : petit prix, meilleure marge du catalogue
    "HNB-078": 1200,  # Estampe : marge élevée, forte rotation
    "HNB-083": 1800,  # Lanterne Ramen
    "HNB-071": 1500,  # Kokeshi Hana
    "HNB-074": 3100,  # Figurine Ryū
    "HNB-018": 2400,  # Maneki-neko Doré : marge la plus faible
    "HNB-064": 3000,  # Masque Hannya : cher, peu vendu, peu rentable
}


PROMOS = [
    ("BIENVENUE10", "percent", 10, None, 0),
    ("DROP5",       "fixed",   None, 500, 3000),
    ("PORTOFFERT",  "free_shipping", None, None, 0),
]

REVIEWS = {
    "HNB-021": [("Yuki M.", 5, "Lumière parfaite pour la chambre, le rouge du torii est superbe la nuit."),
                ("Sofiane B.", 4, "Trois intensités bien pensées, câble un peu court.")],
    "HNB-061": [("Camille R.", 5, "Plus fin qu'attendu, le cordon tient bien au mur.")],
    "HNB-067": [("Léa F.", 5, "J'ai peint le premier œil le jour même. Le rouge est superbe."),
                ("Marc D.", 4, "Un peu plus petit qu'imaginé, mais très bien fait."),
                ("Inès P.", 5, "Qualité au-dessus du prix.")],
    "HNB-037": [("Théo L.", 5, "Bois solide, papier épais, se déplie sans accroc.")],
    "HNB-078": [("Sarah K.", 5, "Papier épais, bleus profonds, encadrée en dix minutes."),
                ("Paul V.", 4, "Belle reproduction, prévoir un cadre aux dimensions exactes.")],
    "HNB-052": [("Nina T.", 5, "Peinture nette, aucune bavure, socle stable.")],
    "HNB-026": [("Adam C.", 5, "Les enfants adorent, la télécommande marche bien."),
                ("Lou R.", 4, "Rendu lune réaliste, batterie correcte.")],
}


def seed(db: Session) -> None:
    if db.query(models.Product).first():
        return

    code_to_id: dict[str, int] = {}
    for code, name, cat, blurb, price, stock, is_new in PRODUCTS:
        art = PHOTOS[code]
        p = models.Product(code=code, name=name, category=cat, blurb=blurb,
                            price_cents=price, cost_cents=COUTS.get(code, 0),
                            stock=stock, is_new=is_new, art=art,
                            images=json.dumps([art]))
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
