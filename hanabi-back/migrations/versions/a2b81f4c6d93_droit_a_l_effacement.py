"""droit a l effacement

Revision ID: a2b81f4c6d93
Revises: f7d43a1b8e05
Create Date: 2026-08-16 09:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2b81f4c6d93"
down_revision: Union[str, None] = "f7d43a1b8e05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable : les comptes existants n'ont evidemment pas ete anonymises, et
    # `NULL` dit exactement cela. Une valeur par defaut serait une affirmation.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("anonymise_le", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("anonymise_le")
