"""courriels de compte

Confirmation d'adresse et reinitialisation de mot de passe : deux parcours qui
passent par un lien recu sur la boite, donc par un jeton a usage unique.

  - `tokens` : jetons stockes HACHES, dates, a usage unique.
  - `users.email_verified` : adresse confirmee par un lien recu sur cette
    adresse. Le compte reste utilisable sans, le drapeau sert a ne pas ecrire a
    une adresse jamais confirmee.

Revision ID: e5c92f18b740
Revises: d3a71c4e9f20
Create Date: 2026-08-15 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5c92f18b740"
down_revision: Union[str, None] = "d3a71c4e9f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `server_default` obligatoire : la colonne est NOT NULL et la table contient
    # deja cent mille comptes, auxquels le moteur doit pouvoir donner une valeur.
    # C'est le piege le plus courant de l'ajout de colonne, et il ne se voit pas
    # sur une base de developpement vide.
    #
    # Les comptes existants passent a `false` : aucun n'a jamais confirme son
    # adresse, puisque le mecanisme n'existait pas. Les marquer confirmes serait
    # une affirmation fausse inscrite en base.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "email_verified", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )

    op.create_table(
        "tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usage", sa.String(length=30), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # Unique : c'est la cle de recherche, et deux empreintes identiques
        # signaleraient un tirage defaillant plutot qu'une coincidence.
        sa.Column("empreinte", sa.String(length=64), nullable=False),
        sa.Column("expire_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utilise_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tokens_empreinte", "tokens", ["empreinte"], unique=True)
    op.create_index("ix_tokens_usage", "tokens", ["usage"], unique=False)
    op.create_index("ix_tokens_user_id", "tokens", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tokens_user_id", table_name="tokens")
    op.drop_index("ix_tokens_usage", table_name="tokens")
    op.drop_index("ix_tokens_empreinte", table_name="tokens")
    op.drop_table("tokens")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("email_verified")
