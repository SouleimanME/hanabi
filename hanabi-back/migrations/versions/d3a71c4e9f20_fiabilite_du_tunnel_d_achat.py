"""fiabilite du tunnel d achat

Trois ajouts qui vont ensemble, parce qu'ils repondent au meme risque : une
commande passee une seule fois par l'acheteur ne doit produire qu'une commande,
qu'un debit et qu'un courriel, quoi qu'il arrive au reseau entre les deux.

  - `idempotency_keys` : trace des requetes non rejouables et de leur reponse.
  - `outbox_emails` : file des courriels, ecrite dans la transaction de la
    commande et videe ensuite par une tache de fond.
  - `orders.payment_ref` : reference d'autorisation du paiement, seul moyen de
    rapprocher une commande d'un mouvement bancaire.

Revision ID: d3a71c4e9f20
Revises: c092692a7b8f
Create Date: 2026-08-15 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3a71c4e9f20"
down_revision: Union[str, None] = "c092692a7b8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, donc sans valeur par defaut a fournir : les commandes deja
    # passees n'ont pas de reference d'autorisation et ne peuvent pas en
    # recevoir une retroactivement.
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("payment_ref", sa.String(length=64), nullable=True))

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cle", sa.String(length=128), nullable=False),
        sa.Column("point_entree", sa.String(length=80), nullable=False),
        sa.Column("empreinte", sa.String(length=64), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False),
        sa.Column("code_reponse", sa.Integer(), nullable=True),
        sa.Column("corps_reponse", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # La contrainte porte tout le mecanisme : c'est elle qui arbitre entre
        # deux requetes simultanees portant la meme cle, la ou un `SELECT`
        # prealable laisserait passer le double-clic qu'on cherche a bloquer.
        sa.UniqueConstraint("cle", "point_entree", name="uq_idempotence"),
    )
    # Indexe pour la purge, qui balaie par anciennete.
    op.create_index(
        "ix_idempotency_keys_created_at", "idempotency_keys", ["created_at"], unique=False
    )

    op.create_table(
        "outbox_emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("destinataire", sa.String(length=255), nullable=False),
        sa.Column("sujet", sa.String(length=255), nullable=False),
        sa.Column("texte", sa.Text(), nullable=False),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("statut", sa.String(length=20), nullable=False),
        sa.Column("tentatives", sa.Integer(), nullable=False),
        sa.Column("derniere_erreur", sa.Text(), nullable=True),
        sa.Column("prochaine_tentative", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("envoye_le", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # L'ouvrier ne pose qu'une question, « qu'y a-t-il a envoyer maintenant »,
    # et il la pose en boucle. Sans cet index il balaierait toute la table a
    # chaque tour, messages deja remis compris - dont le nombre ne fait que
    # croitre.
    op.create_index(
        "ix_outbox_a_traiter", "outbox_emails", ["statut", "prochaine_tentative"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_a_traiter", table_name="outbox_emails")
    op.drop_table("outbox_emails")
    op.drop_index("ix_idempotency_keys_created_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_column("payment_ref")
