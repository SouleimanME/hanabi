"""usages des objets

Revision ID: c1a8e5f3b2d7
Revises: b7e4d2a9c613
Create Date: 2026-09-26 00:00:00.000000

Chaque objet reçoit ses usages : ce qu'il est, où il se pose, pour qui. La
recherche les lit, la fiche ne les montre pas. Les objets du catalogue de
départ reçoivent les leurs ; ceux ajoutés par le marchand commencent vides.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a8e5f3b2d7"
down_revision: Union[str, None] = "b7e4d2a9c613"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Copie figée : cette migration ne suit pas les évolutions de usages.py
USAGES = {
    'HNB-052': "Kitsune, l'esprit renard du folklore japonais, un yokai messager d'Inari\nFigurine à poser sur une étagère, un bureau ou une bibliothèque\nCadeau pour un amateur de mythologie japonaise, de yokai ou d'animés",
    'HNB-018': "Le chat qui salue de la patte, porte-bonheur japonais qui attire la chance et la prospérité\nSe pose à l'entrée d'une boutique, d'un restaurant ou près d'une caisse\nFonctionne à la lumière, sans pile\nCadeau pour une inauguration, un nouveau travail ou un nouveau logement",
    'HNB-067': 'Poupée de vœux japonaise : on peint un œil en formulant un souhait, le second quand il se réalise\nSymbole de persévérance et de réussite, pour un examen, un projet ou la nouvelle année\nPorte-bonheur à poser sur un bureau',
    'HNB-071': "Poupée japonaise traditionnelle en bois, originaire du nord du Japon\nDécoration pour une étagère, une commode ou une chambre\nCadeau de naissance ou d'amitié, artisanat tourné et peint à la main",
    'HNB-074': "Dragon japonais, gardien de l'eau, symbole de force et de sagesse\nFigurine de collection pour un bureau ou une vitrine\nCadeau pour un amateur de dragons, de mythologie ou de fantasy",
    'HNB-037': 'Éventail pliant japonais, à ouvrir en été ou à exposer ouvert au mur\nDécoration murale légère, pour un salon ou un bureau\nAccessoire de cérémonie, de danse ou de costume',
    'HNB-061': "Masque de renard des fêtes et des matsuri japonais, lié aux esprits yokai\nDécoration murale à accrocher, ou masque à porter pour un costume ou un cosplay\nCadeau pour un fan d'animés, de yokai ou de culture japonaise",
    'HNB-064': "Masque de démon du théâtre nô, une femme changée en démon par la jalousie\nDécoration murale forte pour un salon, un bureau ou un dojo\nPour les amateurs de théâtre japonais, de tatouage traditionnel ou d'arts martiaux",
    'HNB-078': "Reproduction de l'estampe ukiyo-e de Hokusai, la grande vague au large de Kanagawa\nTableau à encadrer, art mural pour un salon, une chambre ou un bureau\nCadeau pour un amateur d'art japonais, de la mer ou du surf",
    'HNB-021': 'Veilleuse en forme de torii, le portail des sanctuaires shinto\nLumière douce pour une chambre, une table de chevet ou un bureau\nAlimentée par USB, trois niveaux de lumière',
    'HNB-026': "Lampe en forme de pleine lune, lumière douce et colorée\nVeilleuse pour une chambre d'enfant ou une table de chevet, ambiance de salon\nCadeau pour un enfant, un adolescent ou un amateur d'astronomie",
    'HNB-083': "Lanterne chōchin comme celles des échoppes de ramen et des izakaya\nÉclairage d'ambiance chaleureux pour un salon, une cuisine, un bar ou un balcon\nDécoration pour une soirée japonaise ou un restaurant",
}

produits = sa.table("products", sa.column("code", sa.String), sa.column("usages", sa.Text))


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("usages", sa.Text(), nullable=False, server_default=""))
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column("usages", existing_type=sa.Text(), server_default=None)

    for code, usages in USAGES.items():
        op.execute(
            produits.update()
            .where(produits.c.code == code)
            .values(usages=usages)
        )


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("usages")
