"""catégorie figée à l'achat

Revision ID: b7e4d2a9c613
Revises: f3c9a1d7e2b6
Create Date: 2026-09-24 00:00:00.000000

Chaque ligne de commande garde la catégorie de son produit au moment de l'achat,
comme son prix et son coût : un objet reclassé ne réécrit plus le chiffre
d'affaires passé de sa catégorie. Les lignes existantes prennent la catégorie
actuelle de leur produit, la seule connue.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e4d2a9c613"
down_revision: Union[str, None] = "f3c9a1d7e2b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(length=40), nullable=True))

    op.execute(
        "update order_items set category = "
        "(select category from products where products.id = order_items.product_id)"
    )

    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.alter_column("category", existing_type=sa.String(length=40), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.drop_column("category")
