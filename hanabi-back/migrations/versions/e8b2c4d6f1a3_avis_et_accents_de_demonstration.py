"""avis et accents de démonstration

Revision ID: e8b2c4d6f1a3
Revises: d4e7a9b1c2f3
Create Date: 2026-09-22 00:00:00.000000

Les bases déjà peuplées gardaient la première version du jeu de démonstration :
noms, villes et adresses sans accents (« Timothee », « Orleans »), et douze
avis tirés au hasard, sans rapport avec la note, souvent répétés côte à côte.

Ne touche que la population générée, reconnue au condensat bcrypt qu'elle
partage ; un vrai compte a le sien. Copie figée des listes de `demo_data.py`.
"""
import random
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8b2c4d6f1a3"
down_revision: Union[str, None] = "d4e7a9b1c2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Au-delà, un condensat partagé ne peut être que celui de la population générée
SEUIL_POPULATION = 100

GRAINE = 20260731

ACCENTS = {
    "Anais": "Anaïs", "Andre": "André", "Andrea": "Andréa", "Besancon": "Besançon",
    "Bat.": "Bât.", "Chambery": "Chambéry", "Chloe": "Chloé", "Clement": "Clément",
    "Celia": "Célia", "Come": "Côme", "Francois": "François", "Guerin": "Guérin",
    "Gerard": "Gérard", "Ines": "Inès", "Jaures": "Jaurès", "Lefevre": "Lefèvre",
    "Lea": "Léa", "Leo": "Léo", "Marche": "Marché", "Mael": "Maël", "Maelys": "Maëlys",
    "Noel": "Noël", "Nimes": "Nîmes", "Oceane": "Océane", "Orleans": "Orléans",
    "Raphael": "Raphaël", "Republique": "République", "Residence": "Résidence",
    "Salome": "Salomé", "Solene": "Solène", "Theo": "Théo", "Timothee": "Timothée",
    "Traore": "Traoré", "Zoe": "Zoé", "allee": "allée", "Ecoles": "Écoles",
    "Elise": "Élise", "Emile": "Émile", "etage": "étage",
}

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

# Avis du catalogue initial, écrit avec une faute d'accord
AVIS_CORRIGES = {
    "La laque est magnifique, bien équilibrées en main.":
        "La laque est magnifique, et elles sont bien équilibrées en main.",
}

_MOT = re.compile(r"[A-Za-z]+\.?")


def _accentuer(texte):
    if not texte:
        return texte
    return _MOT.sub(lambda m: ACCENTS.get(m.group(0), m.group(0)), texte)


def _auteur(nom):
    morceaux = (nom or "Client X").split()
    return f"{morceaux[0]} {morceaux[-1][:1]}."


def upgrade() -> None:
    cx = op.get_bind()

    for ancien, nouveau in AVIS_CORRIGES.items():
        cx.execute(
            sa.text("update reviews set text = :nouveau where text = :ancien"),
            {"ancien": ancien, "nouveau": nouveau},
        )

    ligne = cx.execute(
        sa.text(
            "select password_hash, count(*) as n from users "
            "where password_hash like '$2%' "
            "group by password_hash order by n desc limit 1"
        )
    ).first()
    if ligne is None or ligne[1] < SEUIL_POPULATION:
        return
    condensat = ligne[0]

    # --- Accents des comptes générés ---
    comptes = cx.execute(
        sa.text("select id, name, city, addr, addr_extra from users where password_hash = :h"),
        {"h": condensat},
    ).all()
    noms = {}
    corrections = []
    for identifiant, nom, ville, adresse, complement in comptes:
        propres = (_accentuer(nom), _accentuer(ville), _accentuer(adresse), _accentuer(complement))
        noms[identifiant] = propres[0]
        if propres != (nom, ville, adresse, complement):
            corrections.append({
                "id": identifiant, "nom": propres[0], "ville": propres[1],
                "adresse": propres[2], "complement": propres[3],
            })
    if corrections:
        cx.execute(
            sa.text(
                "update users set name = :nom, city = :ville, addr = :adresse, "
                "addr_extra = :complement where id = :id"
            ),
            corrections,
        )

    # --- Avis des comptes générés : texte selon la note, auteur accentué ---
    avis = cx.execute(
        sa.text(
            "select r.id, r.product_id, r.user_id, r.rating, r.verified, r.created_at "
            "from reviews r join users u on u.id = r.user_id "
            "where u.password_hash = :h"
        ),
        {"h": condensat},
    ).all()

    par_produit = {}
    for a in avis:
        par_produit.setdefault(a.product_id, []).append(a)

    tirage = random.Random(GRAINE)
    mises_a_jour = []
    for produit in sorted(par_produit):
        # Ordre d'affichage de la fiche : vérifiés d'abord, puis les plus récents
        lignes = sorted(par_produit[produit], key=lambda a: (bool(a.verified), a.created_at), reverse=True)
        reserves = {}
        for a in lignes:
            note = a.rating if a.rating in AVIS_PAR_NOTE else 3
            reserve = reserves.get(note)
            if not reserve:
                reserve = list(AVIS_PAR_NOTE[note])
                tirage.shuffle(reserve)
                reserves[note] = reserve
            mises_a_jour.append({
                "id": a.id,
                "texte": reserve.pop(),
                "auteur": _auteur(noms.get(a.user_id)),
            })
    if mises_a_jour:
        cx.execute(
            sa.text("update reviews set text = :texte, author_name = :auteur where id = :id"),
            mises_a_jour,
        )


def downgrade() -> None:
    # Correction de données : l'ancienne version n'est pas rétablie
    pass
