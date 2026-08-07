"""cout d achat des produits

Ajoute le cout d'achat unitaire, sans lequel le back-office ne mesure que du
chiffre d'affaires et jamais ce que la boutique gagne.

Revision ID: c092692a7b8f
Revises: 1bfe2ed7ee0a
Create Date: 2026-07-31 20:58:39.046200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c092692a7b8f'
down_revision: Union[str, None] = '1bfe2ed7ee0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `server_default` ajoute a la main : l'autogeneration produisait une
    # colonne NOT NULL sans valeur par defaut, ce qui echoue des que la table
    # contient une ligne - le moteur ne sait pas quoi y mettre. C'est le piege
    # le plus courant de l'ajout de colonne, et il ne se voit pas sur une base
    # de developpement vide.
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0")
        )

    # Meme colonne sur les lignes de commande : la marge d'une commande passee
    # doit rester celle qu'elle a degagee, meme si le tarif fournisseur change
    # ensuite.
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("unit_cost_cents", sa.Integer(), nullable=False, server_default="0")
        )

    # Les valeurs par defaut n'avaient d'utilite que pour remplir les lignes
    # existantes. On les retire ensuite : c'est l'application qui decide d'un
    # cout, pas le schema.
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column("cost_cents", server_default=None)
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.alter_column("unit_cost_cents", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.drop_column("unit_cost_cents")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("cost_cents")
