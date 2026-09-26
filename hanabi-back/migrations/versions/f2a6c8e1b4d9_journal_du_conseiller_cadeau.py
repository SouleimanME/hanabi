"""journal du conseiller cadeau

Revision ID: f2a6c8e1b4d9
Revises: e4c7a1f9d2b8
Create Date: 2026-09-26 16:00:00.000000

Chaque demande au conseiller cadeau laisse une ligne : l'heure, l'issue, le
nombre d'objets proposés. Ni le texte de la demande, ni l'adresse IP : compter
les lignes du jour suffit à borner le coût.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a6c8e1b4d9"
down_revision: Union[str, None] = "e4c7a1f9d2b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conseils",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False),
        sa.Column("choix", sa.Integer(), nullable=False),
        sa.Column("duree_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("conseils", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_conseils_created_at"), ["created_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("conseils", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_conseils_created_at"))
    op.drop_table("conseils")
