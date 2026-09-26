"""fiches multilingues

Revision ID: d8f2b6a4c931
Revises: c1a8e5f3b2d7
Create Date: 2026-09-26 12:00:00.000000

Les traductions anglaises et espagnoles vivaient dans le code : un objet ajouté
depuis le back-office restait en français sur les deux autres versions du site.
Elles passent en base avec leurs usages, que la recherche lit dans chaque
langue, et chaque objet reçoit un texte alternatif pour sa photo principale.
Le catalogue de départ reçoit ses traductions ; les objets du marchand
commencent sans, et s'affichent en français d'ici là.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8f2b6a4c931"
down_revision: Union[str, None] = "c1a8e5f3b2d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Copie figée : cette migration ne suit pas les évolutions de translations.py
TRADUCTIONS = {
    "HNB-052": {
        "en": {
            "name": "Kitsune Figure",
            "blurb": "Resin fox, hand-painted, 18 cm",
            "usages": "Kitsune, the fox spirit of Japanese folklore, a yokai messenger of Inari\nFigure for a shelf, a desk or a bookcase\nGift for a fan of Japanese mythology, yokai or anime"
        },
        "es": {
            "name": "Figura Kitsune",
            "blurb": "Zorro de resina, pintado a mano, 18 cm",
            "usages": "Kitsune, el espíritu zorro del folclore japonés, un yokai mensajero de Inari\nFigura para una estantería, un escritorio o una librería\nRegalo para un aficionado a la mitología japonesa, a los yokai o al anime"
        }
    },
    "HNB-018": {
        "en": {
            "name": "Golden Maneki-neko",
            "blurb": "Lucky cat, solar-powered waving arm",
            "usages": "The cat that waves its paw, a Japanese lucky charm that brings luck and prosperity\nSits at the entrance of a shop, a restaurant or near a till\nRuns on light, no battery\nGift for an opening, a new job or a new home"
        },
        "es": {
            "name": "Maneki-neko Dorado",
            "blurb": "Gato de la suerte, brazo solar motorizado",
            "usages": "El gato que saluda con la pata, amuleto japonés que atrae la suerte y la prosperidad\nSe coloca a la entrada de una tienda, de un restaurante o junto a una caja\nFunciona con luz, sin pilas\nRegalo para una inauguración, un nuevo trabajo o una casa nueva"
        }
    },
    "HNB-067": {
        "en": {
            "name": "Red Daruma",
            "blurb": "Papier-mâché, eyes left to paint, 12 cm",
            "usages": "Japanese wish doll: paint one eye when making a wish, the second when it comes true\nSymbol of perseverance and success, for an exam, a project or the new year\nLucky charm for a desk"
        },
        "es": {
            "name": "Daruma Rojo",
            "blurb": "Papel maché, ojos por pintar, 12 cm",
            "usages": "Muñeco de los deseos japonés: se pinta un ojo al pedir un deseo y el otro cuando se cumple\nSímbolo de perseverancia y éxito, para un examen, un proyecto o el año nuevo\nAmuleto de la suerte para un escritorio"
        }
    },
    "HNB-071": {
        "en": {
            "name": "Hana Kokeshi",
            "blurb": "Turned wood, hand-painted flowers, 10 cm",
            "usages": "Traditional Japanese wooden doll from northern Japan\nDecoration for a shelf, a chest of drawers or a bedroom\nBirth or friendship gift, turned and hand-painted craft"
        },
        "es": {
            "name": "Kokeshi Hana",
            "blurb": "Madera torneada, flores pintadas a mano, 10 cm",
            "usages": "Muñeca japonesa tradicional de madera, originaria del norte de Japón\nDecoración para una estantería, una cómoda o un dormitorio\nRegalo de nacimiento o de amistad, artesanía torneada y pintada a mano"
        }
    },
    "HNB-074": {
        "en": {
            "name": "Ryū Dragon Figure",
            "blurb": "Lacquered resin dragon, crystal pearl, 15 cm",
            "usages": "Japanese dragon, guardian of water, symbol of strength and wisdom\nCollectible figure for a desk or a display cabinet\nGift for a fan of dragons, mythology or fantasy"
        },
        "es": {
            "name": "Figura Ryū",
            "blurb": "Dragón de resina lacada, perla de cristal, 15 cm",
            "usages": "Dragón japonés, guardián del agua, símbolo de fuerza y sabiduría\nFigura de colección para un escritorio o una vitrina\nRegalo para un aficionado a los dragones, la mitología o la fantasía"
        }
    },
    "HNB-037": {
        "en": {
            "name": "Sensu Folding Fan",
            "blurb": "Bamboo and washi paper, wall stand included",
            "usages": "Japanese folding fan, to open in summer or display open on a wall\nLight wall decoration for a living room or an office\nAccessory for ceremonies, dance or costumes"
        },
        "es": {
            "name": "Abanico Sensu",
            "blurb": "Bambú y papel washi, soporte de pared incluido",
            "usages": "Abanico plegable japonés, para abrir en verano o exponer abierto en la pared\nDecoración mural ligera, para un salón o un despacho\nAccesorio de ceremonia, de baile o de disfraz"
        }
    },
    "HNB-061": {
        "en": {
            "name": "Kitsune Mask",
            "blurb": "Hand-painted resin, silk cord, ready to hang",
            "usages": "Fox mask from Japanese festivals and matsuri, linked to yokai spirits\nWall decoration to hang, or a mask to wear for a costume or cosplay\nGift for a fan of anime, yokai or Japanese culture"
        },
        "es": {
            "name": "Máscara Kitsune",
            "blurb": "Resina pintada a mano, cordón de seda, para colgar",
            "usages": "Máscara de zorro de las fiestas y los matsuri japoneses, ligada a los espíritus yokai\nDecoración mural para colgar, o máscara para llevar en un disfraz o un cosplay\nRegalo para un fan del anime, de los yokai o de la cultura japonesa"
        }
    },
    "HNB-064": {
        "en": {
            "name": "Hannya Mask",
            "blurb": "Resin wall mask, gilded horns, 22 cm",
            "usages": "Demon mask from Noh theatre, a woman turned into a demon by jealousy\nStriking wall decoration for a living room, an office or a dojo\nFor fans of Japanese theatre, traditional tattoos or martial arts"
        },
        "es": {
            "name": "Máscara Hannya",
            "blurb": "Máscara mural de resina, cuernos dorados, 22 cm",
            "usages": "Máscara de demonio del teatro noh, una mujer convertida en demonio por los celos\nDecoración mural impactante para un salón, un despacho o un dojo\nPara aficionados al teatro japonés, al tatuaje tradicional o a las artes marciales"
        }
    },
    "HNB-078": {
        "en": {
            "name": "Great Wave Print",
            "blurb": "After Hokusai, printed on washi paper, 30 × 40 cm",
            "usages": "Reproduction of Hokusai's ukiyo-e print, the great wave off Kanagawa\nPicture to frame, wall art for a living room, a bedroom or an office\nGift for a lover of Japanese art, the sea or surfing"
        },
        "es": {
            "name": "Estampa La Gran Ola",
            "blurb": "Según Hokusai, impresa en papel washi, 30 × 40 cm",
            "usages": "Reproducción de la estampa ukiyo-e de Hokusai, la gran ola de Kanagawa\nCuadro para enmarcar, arte mural para un salón, un dormitorio o un despacho\nRegalo para un amante del arte japonés, del mar o del surf"
        }
    },
    "HNB-021": {
        "en": {
            "name": "Torii LED Lamp",
            "blurb": "Torii night light, USB, three brightness levels",
            "usages": "Night light shaped like a torii, the gate of Shinto shrines\nSoft light for a bedroom, a bedside table or a desk\nUSB powered, three brightness levels"
        },
        "es": {
            "name": "Lámpara Torii LED",
            "blurb": "Luz nocturna torii, USB, tres intensidades",
            "usages": "Luz nocturna con forma de torii, el portal de los santuarios sintoístas\nLuz suave para un dormitorio, una mesita de noche o un escritorio\nAlimentada por USB, tres niveles de luz"
        }
    },
    "HNB-026": {
        "en": {
            "name": "Moon Lamp",
            "blurb": "Moon lamp, 16 colors, remote control",
            "usages": "Full moon lamp, soft and colourful light\nNight light for a child's room or a bedside table, living room ambience\nGift for a child, a teenager or an astronomy lover"
        },
        "es": {
            "name": "Lámpara Luna",
            "blurb": "Lámpara luna, 16 colores, mando a distancia",
            "usages": "Lámpara con forma de luna llena, luz suave y de colores\nLuz nocturna para un cuarto infantil o una mesita de noche, ambiente de salón\nRegalo para un niño, un adolescente o un aficionado a la astronomía"
        }
    },
    "HNB-083": {
        "en": {
            "name": "Ramen Lantern",
            "blurb": "Paper and bamboo chōchin, warm LED, 45 cm",
            "usages": "Chōchin lantern like those of ramen stalls and izakaya\nWarm ambient lighting for a living room, a kitchen, a bar or a balcony\nDecoration for a Japanese-themed evening or a restaurant"
        },
        "es": {
            "name": "Farol Ramen",
            "blurb": "Chōchin de papel y bambú, LED cálido, 45 cm",
            "usages": "Farol chōchin como los de los puestos de ramen y las izakaya\nIluminación ambiental cálida para un salón, una cocina, un bar o un balcón\nDecoración para una velada japonesa o un restaurante"
        }
    }
}

produits = sa.table("products", sa.column("code", sa.String), sa.column("traductions", sa.Text))


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("alt", sa.String(length=300), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("traductions", sa.Text(), nullable=False, server_default="{}"))
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.alter_column("alt", existing_type=sa.String(length=300), server_default=None)
        batch_op.alter_column("traductions", existing_type=sa.Text(), server_default=None)

    for code, traductions in TRADUCTIONS.items():
        op.execute(
            produits.update()
            .where(produits.c.code == code)
            .values(traductions=json.dumps(traductions, ensure_ascii=False))
        )


def downgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("traductions")
        batch_op.drop_column("alt")
