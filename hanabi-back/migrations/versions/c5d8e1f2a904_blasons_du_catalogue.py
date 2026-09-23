"""blasons du catalogue

Revision ID: c5d8e1f2a904
Revises: a1f6c2d3e784
Create Date: 2026-09-15 00:00:00.000000
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5d8e1f2a904"
down_revision: Union[str, None] = "a1f6c2d3e784"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BLASONS = {
    "HNB-014": "suzu,#E0452A,#0A0605",
    "HNB-021": "torii,#E0452A,#0A0605",
    "HNB-008": "bandana,#0A0605,#D8452B",
    "HNB-015": "sakura,#E0452A,#EFE7D6",
    "HNB-033": "baguettes,#E0452A,#0A0605",
    "HNB-037": "fan,#0A0605,#D8452B",
    "HNB-041": "bol,#0A0605,#D8452B",
    "HNB-009": "futon,#0A0605,#EFE7D6",
    "HNB-052": "kitsune,#E0452A,#0A0605",
    "HNB-045": "seigaiha,#0A0605,#A83019",
    "HNB-026": "moon,#0A0605,#EFE7D6",
    "HNB-018": "neko,#0A0605,#D8452B",
}

ANCIENS = {
    "HNB-014": "neko,#E0382A,#16140F",
    "HNB-021": "torii,#E0382A,#16140F",
    "HNB-008": "asanoha,#1B3A5B,#E0382A",
    "HNB-015": "sakura,#E0382A,#E8DFC9",
    "HNB-033": "baguettes,#E0382A,#16140F",
    "HNB-037": "fan,#1B3A5B,#E0382A",
    "HNB-041": "bol,#16140F,#E0382A",
    "HNB-009": "wave,#1B3A5B,#E8DFC9",
    "HNB-052": "enso,#E0382A,#1B3A5B",
    "HNB-045": "wave,#16140F,#C9A24B",
    "HNB-026": "moon,#1B3A5B,#E8DFC9",
    "HNB-018": "neko,#C9A24B,#16140F",
}

produits = sa.table(
    "products",
    sa.column("code", sa.String),
    sa.column("art", sa.Text),
    sa.column("images", sa.Text),
)


def _galerie(art: str) -> str:
    forme, trace, fond = art.split(",")
    return json.dumps([art, f"{forme},{fond},{trace}", f"{art},gros-plan"])


def _est_photo(valeur: str | None) -> bool:
    return bool(valeur) and valeur.startswith(("http", "data:"))


def _appliquer(visuels: dict[str, str], galerie) -> None:
    connexion = op.get_bind()
    lignes = connexion.execute(
        sa.select(produits.c.code, produits.c.art).where(produits.c.code.in_(list(visuels)))
    ).all()
    for code, art in lignes:
        if _est_photo(art):
            continue
        connexion.execute(
            produits.update()
            .where(produits.c.code == code)
            .values(art=visuels[code], images=galerie(visuels[code]))
        )


def upgrade() -> None:
    _appliquer(BLASONS, _galerie)


def downgrade() -> None:
    _appliquer(ANCIENS, lambda art: json.dumps([art]))
