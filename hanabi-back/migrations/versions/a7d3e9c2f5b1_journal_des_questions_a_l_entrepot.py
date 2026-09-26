"""journal des questions à l'entrepôt

Revision ID: a7d3e9c2f5b1
Revises: f2a6c8e1b4d9
Create Date: 2026-09-27 10:00:00.000000

Chaque question posée en français à l'entrepôt laisse une ligne : l'heure,
la démonstration ou non, l'issue et le nombre d'essais. Ni la question, ni
le SQL : compter les lignes du jour suffit à borner le coût.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7d3e9c2f5b1"
down_revision: Union[str, None] = "f2a6c8e1b4d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "questions_entrepot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("demo", sa.Boolean(), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False),
        sa.Column("tentatives", sa.Integer(), nullable=True),
        sa.Column("duree_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("questions_entrepot", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_questions_entrepot_created_at"), ["created_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("questions_entrepot", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_questions_entrepot_created_at"))
    op.drop_table("questions_entrepot")
