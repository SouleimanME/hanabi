"""déclinaisons

Revision ID: d3a7f1c9e5b2
Revises: c8f2a4d6e1b3
Create Date: 2026-09-28 18:00:00.000000

Un objet peut se vendre en plusieurs déclinaisons (une couleur, son prix,
son stock, sa photo). La ligne de commande retient la déclinaison achetée et
son libellé figé.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3a7f1c9e5b2"
down_revision: Union[str, None] = "c8f2a4d6e1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "variantes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("libelle", sa.String(length=60), nullable=False),
        sa.Column("couleur", sa.String(length=7), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("image", sa.Text(), nullable=False),
        sa.Column("ordre", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("traductions", sa.Text(), nullable=False),
        sa.CheckConstraint("stock >= 0", name="ck_variante_stock_non_negatif"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("variantes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_variantes_product_id"), ["product_id"], unique=False)

    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("variante_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("variante_libelle", sa.String(length=60), nullable=True))
        batch_op.create_foreign_key(
            "fk_order_items_variante_id_variantes", "variantes", ["variante_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("order_items", schema=None) as batch_op:
        batch_op.drop_constraint("fk_order_items_variante_id_variantes", type_="foreignkey")
        batch_op.drop_column("variante_libelle")
        batch_op.drop_column("variante_id")
    with op.batch_alter_table("variantes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_variantes_product_id"))
    op.drop_table("variantes")
