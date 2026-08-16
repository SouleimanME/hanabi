"""moyens de paiement

Cartes enregistrees par un client. La table ne contient NI numero NI
cryptogramme : de quoi reconnaitre une carte a l'ecran, et un jeton opaque du
prestataire pour la debiter. C'est ce qui maintient l'application hors du
perimetre PCI-DSS.

Revision ID: f7d43a1b8e05
Revises: e5c92f18b740
Create Date: 2026-08-15 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7d43a1b8e05"
down_revision: Union[str, None] = "e5c92f18b740"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reseau", sa.String(length=20), nullable=False),
        sa.Column("quatre_derniers", sa.String(length=4), nullable=False),
        sa.Column("exp_mois", sa.Integer(), nullable=False),
        sa.Column("exp_annee", sa.Integer(), nullable=False),
        sa.Column("libelle", sa.String(length=40), nullable=True),
        sa.Column("jeton", sa.String(length=64), nullable=False),
        sa.Column("defaut", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Deux enregistrements du meme moyen de paiement produiraient deux
        # lignes indiscernables a l'ecran.
        sa.UniqueConstraint("jeton", name="uq_moyen_jeton"),
    )
    op.create_index("ix_payment_methods_user_id", "payment_methods", ["user_id"], unique=False)

    # Pas d'index unique sur (user_id, defaut) : PostgreSQL saurait le faire en
    # index PARTIEL sur `defaut IS TRUE`, SQLite non, et un index unique
    # ordinaire interdirait d'avoir deux cartes NON favorites. La regle est
    # appliquee a l'ecriture, en un seul endroit (`routers/compte.py`).


def downgrade() -> None:
    op.drop_index("ix_payment_methods_user_id", table_name="payment_methods")
    op.drop_table("payment_methods")
