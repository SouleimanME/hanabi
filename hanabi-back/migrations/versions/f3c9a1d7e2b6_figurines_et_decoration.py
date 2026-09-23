"""figurines et décoration

Le catalogue de démonstration ne garde que des figurines et des objets de
décoration. Les accessoires pour animaux, la vaisselle et le tenugui quittent
la vitrine : leurs lignes restent en base, désactivées, car des commandes y
renvoient. Sept objets les remplacent. Les cinq qui restent changent de
catégorie, et tous passent en photo.

N'agit que sur le catalogue de démonstration d'origine (reconnu à HNB-021) :
une base neuve reçoit le nouveau catalogue par `seed()`, et un catalogue
remplacé par le marchand n'est pas touché. Une photo déjà posée n'est jamais
écrasée.

L'historique de la population générée (commandes, avis, vues) passe de chaque
série retirée à son équivalent de même popularité : sans cela, les nouveaux
objets n'auraient ni avis ni ventes, et le back-office classerait en tête des
objets qui ne sont plus en vente. Les vrais clients ne sont pas touchés.

Revision ID: f3c9a1d7e2b6
Revises: e8b2c4d6f1a3
Create Date: 2026-09-23 00:00:00.000000
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3c9a1d7e2b6"
down_revision: Union[str, None] = "e8b2c4d6f1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Copies figées : cette migration ne doit pas suivre les évolutions de seed.py.
TEMOIN = "HNB-021"
RETIRES = ("HNB-014", "HNB-008", "HNB-015", "HNB-009", "HNB-033", "HNB-041", "HNB-045")

_U = "https://images.unsplash.com/"
_CARRE = "?w=1200&h=1200&q=80&auto=format&fit=crop"

# code : (catégorie, accroche, nouveau, photo)
GARDES = {
    "HNB-052": ("Figurines", "Renard en résine, peinte main, 18 cm", False,
                _U + "photo-1615961482046-1645fd0c9920" + _CARRE),
    "HNB-018": ("Figurines", "Chat porte-bonheur, bras motorisé solaire", False,
                _U + "photo-1630929927781-cf12ebc522d6" + _CARRE + "&crop=focalpoint&fp-x=0.5&fp-y=0.36&fp-z=1"),
    "HNB-037": ("Décoration", "Bambou et papier washi, support mural inclus", False,
                _U + "photo-1777563878028-7ff03f169216" + _CARRE),
    "HNB-021": ("Luminaires", "Veilleuse torii, USB, trois intensités", True,
                _U + "photo-1538590586149-5fa9291f0de0" + _CARRE),
    "HNB-026": ("Luminaires", "Lampe lune, 16 couleurs, télécommande", False,
                _U + "photo-1632712535563-c30adb9a9e2e" + _CARRE),
}

# État d'avant, pour le retour arrière : (catégorie, accroche, nouveau, blason)
ANCIENS = {
    "HNB-052": ("Collection", "Renard en résine, peinte main, 18 cm", True, "kitsune,#E0452A,#0A0605"),
    "HNB-018": ("Collection", "Chat porte-bonheur, bras motorisé solaire", False, "neko,#0A0605,#D8452B"),
    "HNB-037": ("Tradition", "Éventail pliant, bambou et papier washi", True, "fan,#0A0605,#D8452B"),
    "HNB-021": ("Collection", "Veilleuse torii, USB, trois intensités", True, "torii,#E0452A,#0A0605"),
    "HNB-026": ("Collection", "Lampe lune, 16 couleurs, télécommande", False, "moon,#0A0605,#EFE7D6"),
}

# code, nom, catégorie, accroche, prix, coût, stock, nouveau, photo
NOUVEAUX = [
    ("HNB-067", "Daruma Rouge", "Figurines", "Papier mâché, yeux à peindre, 12 cm",
     2400, 700, 30, False, _U + "photo-1761296123620-1c756e3f6104" + _CARRE),
    ("HNB-071", "Kokeshi Hana", "Figurines", "Bois tourné, fleurs peintes main, 10 cm",
     3400, 1500, 12, False,
     _U + "photo-1640906631464-cc7bebc39d9f" + _CARRE + "&crop=focalpoint&fp-x=0.45&fp-y=0.5&fp-z=1"),
    ("HNB-074", "Figurine Ryū", "Figurines", "Dragon en résine laquée, perle de cristal, 15 cm",
     5600, 3100, 6, True,
     _U + "photo-1761501156501-d6e4fd7cde5f" + _CARRE + "&crop=focalpoint&fp-x=0.6&fp-y=0.55&fp-z=1"),
    ("HNB-061", "Masque Kitsune", "Décoration", "Résine peinte main, cordon de soie, à suspendre",
     3900, 1400, 10, True,
     _U + "photo-1681632973091-1e2725d00da3" + _CARRE + "&crop=focalpoint&fp-x=0.5&fp-y=0.42&fp-z=1"),
    ("HNB-064", "Masque Hannya", "Décoration", "Masque mural en résine, cornes dorées, 22 cm",
     6200, 3000, 5, False,
     _U + "photo-1746987443790-79b01cd6a83f" + _CARRE + "&crop=focalpoint&fp-x=0.5&fp-y=0.5&fp-z=1.7"),
    ("HNB-078", "Estampe Grande Vague", "Décoration",
     "D'après Hokusai, impression sur papier washi, 30 × 40 cm",
     4500, 1200, 20, False,
     _U + "photo-1783958384742-b316026f543c" + _CARRE + "&crop=focalpoint&fp-x=0.33&fp-y=0.5&fp-z=1"),
    ("HNB-083", "Lanterne Ramen", "Luminaires", "Chōchin en papier et bambou, LED chaude, 45 cm",
     4200, 1800, 9, False,
     _U + "photo-1557404756-2896e84ca347" + _CARRE + "&crop=focalpoint&fp-x=0.33&fp-y=0.5&fp-z=1"),
]

# Série retirée : (nom, blason d'origine, équivalent qui reprend son historique
# de démonstration). Les couples suivent les poids de demo_data.POPULARITE.
EQUIVALENTS = {
    "HNB-014": ("Collier Maneki-neko", "suzu,#E0452A,#0A0605", "HNB-061"),
    "HNB-033": ("Baguettes Laquées", "baguettes,#E0452A,#0A0605", "HNB-067"),
    "HNB-041": ("Bol à Ramen", "bol,#0A0605,#D8452B", "HNB-083"),
    "HNB-045": ("Tenugui Seigaiha", "seigaiha,#0A0605,#A83019", "HNB-078"),
    "HNB-008": ("Bandana Sushi", "bandana,#0A0605,#D8452B", "HNB-071"),
    "HNB-015": ("Gamelle Sakura", "sakura,#E0452A,#EFE7D6", "HNB-074"),
    "HNB-009": ("Coussin Futon Néko", "futon,#0A0605,#EFE7D6", "HNB-064"),
}

# Comptes générés : un même condensat partagé par au moins ce nombre de comptes
SEUIL_POPULATION = 100

produits = sa.table(
    "products",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("category", sa.String),
    sa.column("blurb", sa.String),
    sa.column("price_cents", sa.Integer),
    sa.column("cost_cents", sa.Integer),
    sa.column("stock", sa.Integer),
    sa.column("is_new", sa.Boolean),
    sa.column("active", sa.Boolean),
    sa.column("featured", sa.Boolean),
    sa.column("featured_order", sa.Integer),
    sa.column("art", sa.Text),
    sa.column("images", sa.Text),
)

# Tables qui renvoient à un produit : un produit référencé se désactive au
# lieu de disparaître
REFERENCES = ("order_items", "product_views", "reviews", "stock_alerts")


def _est_photo(valeur: str | None) -> bool:
    return bool(valeur) and valeur.startswith(("http", "data:"))


def _galerie_blason(art: str) -> str:
    forme, trace, fond = art.split(",")
    return json.dumps([art, f"{forme},{fond},{trace}", f"{art},gros-plan"])


def _codes(connexion) -> dict[str, tuple[int, str]]:
    return {
        code: (pid, art)
        for pid, code, art in connexion.execute(
            sa.select(produits.c.id, produits.c.code, produits.c.art)
        )
    }


def _condensat_de_demonstration(connexion) -> str | None:
    ligne = connexion.execute(
        sa.text(
            "select password_hash, count(*) as n from users "
            "where password_hash like '$2%' "
            "group by password_hash order by n desc limit 1"
        )
    ).first()
    if ligne is None or ligne[1] < SEUIL_POPULATION:
        return None
    return ligne[0]


def _deplacer_l_historique(connexion, de: int, vers: int, nom: str, art: str, condensat: str) -> None:
    """Commandes, avis et vues des comptes générés passent d'un produit à l'autre."""
    parametres = {"de": de, "vers": vers, "nom": nom, "art": art, "h": condensat}
    connexion.execute(
        sa.text(
            "update order_items set product_id = :vers, name = :nom, art = :art "
            "where product_id = :de and order_id in ("
            "select o.id from orders o join users u on u.id = o.user_id where u.password_hash = :h)"
        ),
        parametres,
    )
    for table in ("reviews", "product_views"):
        connexion.execute(
            sa.text(
                f"update {table} set product_id = :vers where product_id = :de "
                "and user_id in (select id from users where password_hash = :h)"
            ),
            parametres,
        )


def upgrade() -> None:
    connexion = op.get_bind()
    existants = _codes(connexion)
    if TEMOIN not in existants:
        return

    connexion.execute(
        produits.update()
        .where(produits.c.code.in_(RETIRES))
        .values(active=False, is_new=False, featured=False)
    )

    for code, (categorie, accroche, nouveau, photo) in GARDES.items():
        if code not in existants:
            continue
        valeurs = {"category": categorie, "blurb": accroche, "is_new": nouveau}
        if not _est_photo(existants[code][1]):
            valeurs.update(art=photo, images=json.dumps([photo]))
        connexion.execute(produits.update().where(produits.c.code == code).values(**valeurs))

    for code, nom, categorie, accroche, prix, cout, stock, nouveau, photo in NOUVEAUX:
        if code in existants:
            # Resté en base, désactivé, après un retour arrière : il revient en vitrine
            connexion.execute(
                produits.update().where(produits.c.code == code)
                .values(active=True, category=categorie, blurb=accroche)
            )
            continue
        connexion.execute(produits.insert().values(
            code=code, name=nom, category=categorie, blurb=accroche,
            price_cents=prix, cost_cents=cout, stock=stock, is_new=nouveau,
            active=True, featured=False, featured_order=0,
            art=photo, images=json.dumps([photo]),
        ))

    condensat = _condensat_de_demonstration(connexion)
    if condensat is None:
        return
    ids = {code: pid for code, (pid, _) in _codes(connexion).items()}
    nouveaux = {code: (nom, photo) for code, nom, *_, photo in NOUVEAUX}
    for ancien, (_, _, equivalent) in EQUIVALENTS.items():
        if ancien in ids and equivalent in ids:
            nom, photo = nouveaux[equivalent]
            _deplacer_l_historique(connexion, ids[ancien], ids[equivalent], nom, photo, condensat)


def downgrade() -> None:
    connexion = op.get_bind()
    existants = _codes(connexion)
    if TEMOIN not in existants:
        return

    condensat = _condensat_de_demonstration(connexion)
    if condensat is not None:
        ids = {code: pid for code, (pid, _) in existants.items()}
        for ancien, (nom, blason, equivalent) in EQUIVALENTS.items():
            if ancien in ids and equivalent in ids:
                _deplacer_l_historique(connexion, ids[equivalent], ids[ancien], nom, blason, condensat)
        existants = _codes(connexion)

    photos = {ligne[-1] for ligne in NOUVEAUX}
    for code, *_ in NOUVEAUX:
        if code not in existants:
            continue
        pid, art = existants[code]
        if art not in photos:
            continue  # modifié depuis par le marchand : on le laisse
        reference = any(
            connexion.execute(
                sa.text(f"SELECT 1 FROM {table} WHERE product_id = :pid LIMIT 1"), {"pid": pid}
            ).first()
            for table in REFERENCES
        )
        if reference:
            connexion.execute(produits.update().where(produits.c.id == pid).values(active=False))
        else:
            connexion.execute(produits.delete().where(produits.c.id == pid))

    connexion.execute(produits.update().where(produits.c.code.in_(RETIRES)).values(active=True))

    for code, (categorie, accroche, nouveau, blason) in ANCIENS.items():
        if code not in existants:
            continue
        valeurs = {"category": categorie, "blurb": accroche, "is_new": nouveau}
        if existants[code][1] == GARDES[code][3]:
            valeurs.update(art=blason, images=_galerie_blason(blason))
        connexion.execute(produits.update().where(produits.c.code == code).values(**valeurs))
