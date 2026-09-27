"""demandes sans réponse

Revision ID: c8f2a4d6e1b3
Revises: b4e1c7a9d3f2
Create Date: 2026-09-28 12:00:00.000000

Recherches sans résultat et besoins reformulés des demandes au conseiller
restées sans objet, gardés trente jours pour savoir quels objets ajouter.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8f2a4d6e1b3"
down_revision: Union[str, None] = "b4e1c7a9d3f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "demandes_sans_reponse",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("texte", sa.String(length=80), nullable=False),
        sa.Column("lang", sa.String(length=5), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("demandes_sans_reponse", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_demandes_sans_reponse_created_at"), ["created_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("demandes_sans_reponse", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_demandes_sans_reponse_created_at"))
    op.drop_table("demandes_sans_reponse")
