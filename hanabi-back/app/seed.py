# -*- coding: utf-8 -*-
"""Donnees de demarrage, catalogue japonais (drop)."""
import json
import logging

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .passwords import validate_password
from .security import hash_password

log = logging.getLogger("hanabi.seed")

"""Adresse du compte de demonstration, affichee dans l'interface de connexion.
Definie ici pour que le seed et la retrogradation partagent la meme valeur."""
DEMO_EMAIL = "demo@hanabi.fr"

# --- Compte vitrine du back-office ---
#
# Identifiants publics, affiches dans la fenetre de connexion sous ceux du
# compte client. Ils existent pour qu'un recruteur ouvre le back-office sans
# avoir a demander d'acces.
#
# Ils sont ecrits en clair ici, et c'est assume : un secret affiche sur la page
# de connexion n'est pas un secret, le placer en variable d'environnement
# donnerait l'illusion inverse. Le veritable garde-fou est ailleurs - ce compte
# est bride en lecture seule par `DEMO_ADMIN_READONLY` (voir `deps.py`).
#
# L'administrateur reel, lui, reste provisionne par ADMIN_EMAIL /
# ADMIN_PASSWORD et n'apparait jamais dans le depot.
DEMO_ADMIN_EMAIL = "hanabi@atelier.fr"
DEMO_ADMIN_PASSWORD = "hanabi-logs2026"

# code, name, category, blurb, price_cents, stock, is_new, art ("forme,couleur1,couleur2")
PRODUCTS = [
    ("HNB-014", "Collier Maneki-neko", "Compagnons", "Collier chat, grelot laiton, cuir souple",     2400, 12, False, "neko,#E0382A,#16140F"),
    ("HNB-021", "Lampe Torii LED",     "Collection", "Veilleuse torii, USB, trois intensités",        6400, 5,  True,  "torii,#E0382A,#16140F"),
    ("HNB-008", "Bandana Sushi",       "Compagnons", "Bandana chien, coton, taille réglable",         1800, 25, False, "asanoha,#1B3A5B,#E0382A"),
    ("HNB-015", "Gamelle Sakura",      "Compagnons", "Gamelle céramique, motif fleur de cerisier",    3200, 9,  False, "sakura,#E0382A,#E8DFC9"),
    ("HNB-033", "Baguettes Laquées",   "Tradition",  "Paire, laque urushi, repose-baguettes inclus",  2200, 40, False, "baguettes,#E0382A,#16140F"),
    ("HNB-037", "Éventail Sensu",      "Tradition",  "Éventail pliant, bambou et papier washi",       2800, 18, True,  "fan,#1B3A5B,#E0382A"),
    ("HNB-041", "Bol à Ramen",         "Tradition",  "Céramique 1 L, motif vague seigaiha",           2600, 22, False, "bol,#16140F,#E0382A"),
    ("HNB-009", "Coussin Futon Néko",  "Compagnons", "Couchage chat, futon coton matelassé",          5800, 6,  False, "wave,#1B3A5B,#E8DFC9"),
    ("HNB-052", "Figurine Kitsune",    "Collection", "Renard en résine, peinte main, 18 cm",          4800, 4,  True,  "enso,#E0382A,#1B3A5B"),
    ("HNB-045", "Tenugui Seigaiha",    "Tradition",  "Serviette coton, teinture traditionnelle",      1600, 50, False, "wave,#16140F,#C9A24B"),
    ("HNB-026", "Lampe Lune",          "Collection", "Lampe lune, 16 couleurs, télécommande",         7200, 7,  False, "moon,#1B3A5B,#E8DFC9"),
    ("HNB-018", "Maneki-neko Doré",    "Collection", "Chat porte-bonheur, bras motorisé solaire",     3800, 14, False, "neko,#C9A24B,#16140F"),
]

# Cout d'achat unitaire, en centimes.
#
# Volontairement heterogene, parce que c'est ainsi dans le commerce : un objet
# artisanal ne se marge pas comme un textile imprime. C'est cet ecart qui rend
# l'analyse utile - le classement par chiffre d'affaires et le classement par
# marge ne donnent pas le meme podium, et c'est le second qui paie les salaires.
#
# Table separee du tuple produit plutot qu'une colonne de plus dans celui-ci :
# elle se relit d'un coup d'oeil, et le cout est une donnee de gestion qui n'a
# rien a faire au milieu de la fiche publique.
COUTS = {
    "HNB-021": 2900,  # Lampe Torii : 55 % de marge, et le plus gros volume
    "HNB-026": 4300,  # Lampe Lune : chere a l'achat, marge faible
    "HNB-052": 2100,  # Figurine Kitsune
    "HNB-014": 900,   # Collier Maneki-neko
    "HNB-037": 1050,  # Eventail Sensu
    "HNB-033": 700,   # Baguettes : la meilleure marge du catalogue
    "HNB-041": 1000,  # Bol a Ramen
    "HNB-045": 550,   # Tenugui : petit prix, marge elevee, forte rotation
    "HNB-008": 780,   # Bandana Sushi
    "HNB-015": 1600,  # Gamelle Sakura
    "HNB-018": 2400,  # Maneki-neko dore : la moins bonne marge
    "HNB-009": 3500,  # Coussin Futon : cher, peu vendu, peu rentable
}

SHAPES = ["enso", "wave", "fan", "asanoha", "torii", "moon", "sakura", "bol", "baguettes", "neko"]


def gallery(art: str) -> list[str]:
    """Construit une galerie de 3 visuels distincts a partir du visuel principal.
    En prod, on remplacerait par une liste d'URLs d'images reelles."""
    shape, c1, c2 = art.split(",")
    others = [s for s in SHAPES if s != shape]
    return [art, f"{others[1]},{c2},{c1}", f"{others[3]},{c1},{c2}"]


PROMOS = [
    ("BIENVENUE10", "percent", 10, None, 0),
    ("DROP5",       "fixed",   None, 500, 3000),
    ("PORTOFFERT",  "free_shipping", None, None, 0),
]

REVIEWS = {
    "HNB-021": [("Yuki M.", 5, "Lumière parfaite pour la chambre, le rouge du torii est superbe la nuit."),
                ("Sofiane B.", 4, "Trois intensités bien pensées, câble un peu court.")],
    "HNB-014": [("Camille R.", 5, "Mon chat le porte sans broncher, le grelot est discret.")],
    "HNB-033": [("Léa F.", 5, "La laque est magnifique, bien équilibrées en main."),
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

    # Compte de demonstration : un client ordinaire, volontairement SANS droits
    # d'administration. Ses identifiants sont affiches dans la fenetre de
    # connexion pour que l'on puisse essayer le parcours d'achat ; le back-office
    # serait donc ouvert a tout visiteur si ce compte etait administrateur.
    # L'administrateur est provisionne separement, voir `ensure_admin`.
    db.add(models.User(
        name="Souleyman Demo", email=DEMO_EMAIL,
        password_hash=hash_password("demo1234"), is_admin=False,
    ))
    db.commit()


def _demote_public_demo(db: Session) -> None:
    """Retire les droits d'administration au compte de demonstration.

    Necessaire pour les bases creees avant la separation des deux comptes :
    `seed` s'interrompt des que le catalogue existe, si bien qu'une base deja
    en service garderait un compte administrateur dont les identifiants sont
    affiches dans l'interface. Le correctif ne protegerait alors que les
    installations neuves.

    Ne touche a rien si ce compte est justement celui designe par ADMIN_EMAIL :
    on suppose alors le choix delibere.
    """
    demo = db.query(models.User).filter(models.User.email == DEMO_EMAIL).first()
    if demo is None or not demo.is_admin:
        return
    if settings.ADMIN_EMAIL.strip().lower() == DEMO_EMAIL:
        return

    demo.is_admin = False
    db.commit()
    log.warning(
        "Droits d'administration retires a %s : ses identifiants sont publics. "
        "Utilise ADMIN_EMAIL / ADMIN_PASSWORD pour designer un administrateur.",
        DEMO_EMAIL,
    )


def ensure_public_admin(db: Session) -> None:
    """Cree ou remet a niveau le compte vitrine du back-office.

    Executee a chaque demarrage, comme `ensure_admin`, pour la meme raison :
    la base de l'hebergement gratuit est reconstruite a chaque redeploiement.

    Deux details qui ne sautent pas aux yeux :

    - le mot de passe est reapplique a chaque passage. Sans cela, changer la
      constante ci-dessus n'aurait aucun effet sur une base existante, et les
      identifiants affiches dans l'interface finiraient par ne plus ouvrir
      quoi que ce soit ;
    - `validate_password` n'est volontairement pas consultee. Elle refuserait
      ce mot de passe, qui reprend la partie locale de l'adresse - et elle a
      raison de le faire pour un compte que l'on cherche a proteger. Ici, la
      contrainte est inverse : les identifiants doivent etre memorisables et
      sont publies. La regle continue de s'appliquer aux inscriptions et a
      l'administrateur reel, ou elle a un sens.
    """
    if not settings.PUBLIC_ADMIN_DEMO:
        return

    compte = db.query(models.User).filter(models.User.email == DEMO_ADMIN_EMAIL).first()
    if compte is None:
        db.add(models.User(
            name="Back-office (demonstration)",
            email=DEMO_ADMIN_EMAIL,
            password_hash=hash_password(DEMO_ADMIN_PASSWORD),
            is_admin=True,
        ))
        db.commit()
        log.warning(
            "Compte vitrine du back-office cree : %s (lecture seule : %s)",
            DEMO_ADMIN_EMAIL, settings.DEMO_ADMIN_READONLY,
        )
        return

    compte.is_admin = True
    compte.password_hash = hash_password(DEMO_ADMIN_PASSWORD)
    db.commit()


def ensure_admin(db: Session) -> None:
    """Cree ou promeut le compte administrateur decrit par l'environnement.

    Volontairement separe de `seed` : celui-ci s'interrompt des que le catalogue
    existe, si bien qu'un administrateur ajoute apres la premiere mise en service
    ne serait jamais cree. Cette fonction s'execute a chaque demarrage et est
    idempotente.

    Sans ADMIN_EMAIL ni ADMIN_PASSWORD, aucun administrateur n'est cree : la
    boutique fonctionne, seul le back-office reste inaccessible. C'est le
    comportement voulu par defaut, pour qu'une mise en ligne distraite n'expose
    pas l'administration.
    """
    # D'abord refermer la porte, ensuite ouvrir la bonne : sur une base ancienne,
    # le compte de demonstration est encore administrateur.
    _demote_public_demo(db)

    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        log.info(
            "Aucun administrateur provisionne (ADMIN_EMAIL / ADMIN_PASSWORD absents). "
            "Le back-office restera inaccessible."
        )
        return

    email = settings.ADMIN_EMAIL.strip().lower()

    # Un administrateur au mot de passe trivial annule l'interet de la mesure.
    problem = validate_password(settings.ADMIN_PASSWORD, email=email)
    if problem:
        log.error("ADMIN_PASSWORD refuse : %s Aucun administrateur cree.", problem)
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
    log.warning("Compte administrateur cree : %s", email)
