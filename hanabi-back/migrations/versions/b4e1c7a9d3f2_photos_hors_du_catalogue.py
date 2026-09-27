"""photos hors du catalogue

Revision ID: b4e1c7a9d3f2
Revises: a7d3e9c2f5b1
Create Date: 2026-09-28 10:00:00.000000

Les photos téléversées vivaient en `data:` dans `products.art`,
`products.images` et `order_items.art` : chaque liste de produits les
renvoyait toutes. Elles passent dans `medias`, sous l'empreinte de leur
contenu, et les fiches ne gardent que `/media/<empreinte>`. Le retour arrière
les remet en place.
"""
import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4e1c7a9d3f2"
down_revision: Union[str, None] = "a7d3e9c2f5b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DATA = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$")
PREFIXE = "/media/"

medias = sa.table(
    "medias",
    sa.column("empreinte", sa.String),
    sa.column("type", sa.String),
    sa.column("octets", sa.LargeBinary),
    sa.column("created_at", sa.DateTime(timezone=True)),
)
products = sa.table(
    "products", sa.column("id", sa.Integer), sa.column("art", sa.Text), sa.column("images", sa.Text)
)
order_items = sa.table("order_items", sa.column("id", sa.Integer), sa.column("art", sa.Text))


def _ranger(cx, connus: set[str], valeur):
    m = _DATA.match(valeur) if isinstance(valeur, str) else None
    if not m:
        return valeur
    octets = base64.b64decode(m.group(2))
    empreinte = hashlib.sha256(octets).hexdigest()
    if empreinte not in connus:
        cx.execute(medias.insert().values(
            empreinte=empreinte, type=m.group(1), octets=octets,
            created_at=datetime.now(timezone.utc),
        ))
        connus.add(empreinte)
    return PREFIXE + empreinte


def upgrade() -> None:
    op.create_table(
        "medias",
        sa.Column("empreinte", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("octets", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("empreinte"),
    )
    cx = op.get_bind()
    connus: set[str] = set()
    for id_, art, images in cx.execute(
        sa.select(products.c.id, products.c.art, products.c.images)
        .where(sa.or_(products.c.art.like("data:%"), products.c.images.like("%data:%")))
    ).all():
        try:
            liste = json.loads(images) if images else []
        except ValueError:
            liste = []
        cx.execute(products.update().where(products.c.id == id_).values(
            art=_ranger(cx, connus, art),
            images=json.dumps([_ranger(cx, connus, i) for i in liste]),
        ))
    for id_, art in cx.execute(
        sa.select(order_items.c.id, order_items.c.art).where(order_items.c.art.like("data:%"))
    ).all():
        cx.execute(order_items.update().where(order_items.c.id == id_).values(art=_ranger(cx, connus, art)))


def _remettre(octets_par_chemin: dict[str, str], valeur):
    return octets_par_chemin.get(valeur, valeur) if isinstance(valeur, str) else valeur


def downgrade() -> None:
    cx = op.get_bind()
    chemins = {
        PREFIXE + e: f"data:{t};base64,{base64.b64encode(o).decode()}"
        for e, t, o in cx.execute(sa.select(medias.c.empreinte, medias.c.type, medias.c.octets)).all()
    }
    if chemins:
        for id_, art, images in cx.execute(
            sa.select(products.c.id, products.c.art, products.c.images)
        ).all():
            try:
                liste = json.loads(images) if images else []
            except ValueError:
                liste = []
            cx.execute(products.update().where(products.c.id == id_).values(
                art=_remettre(chemins, art), images=json.dumps([_remettre(chemins, i) for i in liste]),
            ))
        for id_, art in cx.execute(
            sa.select(order_items.c.id, order_items.c.art).where(order_items.c.art.like(PREFIXE + "%"))
        ).all():
            cx.execute(order_items.update().where(order_items.c.id == id_).values(art=_remettre(chemins, art)))
    op.drop_table("medias")
