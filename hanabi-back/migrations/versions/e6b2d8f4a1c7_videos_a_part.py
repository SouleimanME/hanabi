"""vidéos à part

Revision ID: e6b2d8f4a1c7
Revises: d3a7f1c9e5b2
Create Date: 2026-09-28 21:00:00.000000

Un objet peut montrer ses vidéos dans leur propre section plutôt qu'entre
ses photos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6b2d8f4a1c7"
down_revision: Union[str, None] = "d3a7f1c9e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("videos_a_part", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("videos_a_part")
