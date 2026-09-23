"""livraison, alertes et adresses en minuscules

Revision ID: d4e7a9b1c2f3
Revises: c5d8e1f2a904
Create Date: 2026-09-22 00:00:00.000000

- La commande garde l'adresse de livraison saisie au paiement.
- L'alerte de retour en stock garde la langue de la page.
- Les adresses e-mail passent en minuscules : un compte créé depuis un
  téléphone (« Marie@... ») ne retrouvait pas son mot de passe oublié. Une
  adresse dont la forme en minuscules existe déjà reste telle quelle ; la
  connexion la retrouve quand même.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e7a9b1c2f3"
down_revision: Union[str, None] = "c5d8e1f2a904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ship_name", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("ship_addr", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("ship_cp", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("ship_city", sa.String(length=120), nullable=True))

    with op.batch_alter_table("stock_alerts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("lang", sa.String(length=5), nullable=False, server_default="fr")
        )

    # Sans collision seulement : la contrainte d'unicité reste respectée
    op.execute(
        """
        update users set email = lower(email)
        where email <> lower(email)
          and not exists (select 1 from users autre where autre.email = lower(users.email))
        """
    )
    op.execute(
        """
        update stock_alerts set email = lower(email)
        where email <> lower(email)
          and not exists (
            select 1 from stock_alerts autre
            where autre.product_id = stock_alerts.product_id
              and autre.email = lower(stock_alerts.email)
          )
        """
    )
    op.execute("update orders set email = lower(email) where email <> lower(email)")


def downgrade() -> None:
    # Les adresses restent en minuscules : la casse d'origine n'est pas conservée
    with op.batch_alter_table("stock_alerts", schema=None) as batch_op:
        batch_op.drop_column("lang")

    with op.batch_alter_table("orders", schema=None) as batch_op:
        batch_op.drop_column("ship_city")
        batch_op.drop_column("ship_cp")
        batch_op.drop_column("ship_addr")
        batch_op.drop_column("ship_name")
