"""journal de l'assistant de fiche produit

Revision ID: e4c7a1f9d2b8
Revises: d8f2b6a4c931
Create Date: 2026-09-26 14:00:00.000000

Chaque demande à l'assistant laisse une ligne : l'heure, la démonstration ou
non, l'issue. Compter les lignes du jour borne le coût, y compris après un
redémarrage. Aucune ligne ne désigne une personne.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4c7a1f9d2b8"
down_revision: Union[str, None] = "d8f2b6a4c931"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "redactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("demo", sa.Boolean(), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False),
        sa.Column("photo_lue", sa.Boolean(), nullable=False),
        sa.Column("duree_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("redactions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_redactions_created_at"), ["created_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("redactions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_redactions_created_at"))
    op.drop_table("redactions")
