"""cout d achat des produits

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
    # `server_default` ajoute a la main
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("cost_cents", sa.Integer(), nullable=False, server_default="0")
        )

    # Meme colonne sur les lignes de commande
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("unit_cost_cents", sa.Integer(), nullable=False, server_default="0")
        )

    # Les valeurs par defaut n'avaient d'utilite que pour remplir les lignes existantes
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column("cost_cents", server_default=None)
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.alter_column("unit_cost_cents", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.drop_column("unit_cost_cents")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("cost_cents")
