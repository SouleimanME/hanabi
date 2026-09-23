"""acceptation des cgv

Revision ID: b9e35d7a4c18
Revises: a2b81f4c6d93
Create Date: 2026-08-16 11:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9e35d7a4c18"
down_revision: Union[str, None] = "a2b81f4c6d93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable : les commandes anterieures a cette regle n'ont pas d'acceptation
    # tracee, et leur en inventer une serait ecrire une affirmation fausse.
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cgv_version", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("cgv_acceptees_le", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_column("cgv_acceptees_le")
        batch_op.drop_column("cgv_version")
