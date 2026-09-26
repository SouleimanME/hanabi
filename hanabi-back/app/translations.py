# -*- coding: utf-8 -*-
"""Traductions anglaises et espagnoles du catalogue de départ.

Copiées en base par `seed()` et par la migration des fiches multilingues : le
marchand les modifie ensuite dans le back-office. Les usages traduisent
fidèlement ceux de `usages.py`, une ligne pour une ligne.
"""
import json

LANGUES = ("en", "es")

PRODUCT_I18N: dict[str, dict[str, dict[str, str]]] = {
    "HNB-052": {
        "en": {
            "name": "Kitsune Figure",
            "blurb": "Resin fox, hand-painted, 18 cm",
            "usages": "\n".join([
                "Kitsune, the fox spirit of Japanese folklore, a yokai messenger of Inari",
                "Figure for a shelf, a desk or a bookcase",
                "Gift for a fan of Japanese mythology, yokai or anime",
            ]),
        },
        "es": {
            "name": "Figura Kitsune",
            "blurb": "Zorro de resina, pintado a mano, 18 cm",
            "usages": "\n".join([
                "Kitsune, el espíritu zorro del folclore japonés, un yokai mensajero de Inari",
                "Figura para una estantería, un escritorio o una librería",
                "Regalo para un aficionado a la mitología japonesa, a los yokai o al anime",
            ]),
        },
    },
    "HNB-018": {
        "en": {
            "name": "Golden Maneki-neko",
            "blurb": "Lucky cat, solar-powered waving arm",
            "usages": "\n".join([
                "The cat that waves its paw, a Japanese lucky charm that brings luck and prosperity",
                "Sits at the entrance of a shop, a restaurant or near a till",
                "Runs on light, no battery",
                "Gift for an opening, a new job or a new home",
            ]),
        },
        "es": {
            "name": "Maneki-neko Dorado",
            "blurb": "Gato de la suerte, brazo solar motorizado",
            "usages": "\n".join([
                "El gato que saluda con la pata, amuleto japonés que atrae la suerte y la prosperidad",
                "Se coloca a la entrada de una tienda, de un restaurante o junto a una caja",
                "Funciona con luz, sin pilas",
                "Regalo para una inauguración, un nuevo trabajo o una casa nueva",
            ]),
        },
    },
    "HNB-067": {
        "en": {
            "name": "Red Daruma",
            "blurb": "Papier-mâché, eyes left to paint, 12 cm",
            "usages": "\n".join([
                "Japanese wish doll: paint one eye when making a wish, the second when it comes true",
                "Symbol of perseverance and success, for an exam, a project or the new year",
                "Lucky charm for a desk",
            ]),
        },
        "es": {
            "name": "Daruma Rojo",
            "blurb": "Papel maché, ojos por pintar, 12 cm",
            "usages": "\n".join([
                "Muñeco de los deseos japonés: se pinta un ojo al pedir un deseo y el otro cuando se cumple",
                "Símbolo de perseverancia y éxito, para un examen, un proyecto o el año nuevo",
                "Amuleto de la suerte para un escritorio",
            ]),
        },
    },
    "HNB-071": {
        "en": {
            "name": "Hana Kokeshi",
            "blurb": "Turned wood, hand-painted flowers, 10 cm",
            "usages": "\n".join([
                "Traditional Japanese wooden doll from northern Japan",
                "Decoration for a shelf, a chest of drawers or a bedroom",
                "Birth or friendship gift, turned and hand-painted craft",
            ]),
        },
        "es": {
            "name": "Kokeshi Hana",
            "blurb": "Madera torneada, flores pintadas a mano, 10 cm",
            "usages": "\n".join([
                "Muñeca japonesa tradicional de madera, originaria del norte de Japón",
                "Decoración para una estantería, una cómoda o un dormitorio",
                "Regalo de nacimiento o de amistad, artesanía torneada y pintada a mano",
            ]),
        },
    },
    "HNB-074": {
        "en": {
            "name": "Ryū Dragon Figure",
            "blurb": "Lacquered resin dragon, crystal pearl, 15 cm",
            "usages": "\n".join([
                "Japanese dragon, guardian of water, symbol of strength and wisdom",
                "Collectible figure for a desk or a display cabinet",
                "Gift for a fan of dragons, mythology or fantasy",
            ]),
        },
        "es": {
            "name": "Figura Ryū",
            "blurb": "Dragón de resina lacada, perla de cristal, 15 cm",
            "usages": "\n".join([
                "Dragón japonés, guardián del agua, símbolo de fuerza y sabiduría",
                "Figura de colección para un escritorio o una vitrina",
                "Regalo para un aficionado a los dragones, la mitología o la fantasía",
            ]),
        },
    },
    "HNB-037": {
        "en": {
            "name": "Sensu Folding Fan",
            "blurb": "Bamboo and washi paper, wall stand included",
            "usages": "\n".join([
                "Japanese folding fan, to open in summer or display open on a wall",
                "Light wall decoration for a living room or an office",
                "Accessory for ceremonies, dance or costumes",
            ]),
        },
        "es": {
            "name": "Abanico Sensu",
            "blurb": "Bambú y papel washi, soporte de pared incluido",
            "usages": "\n".join([
                "Abanico plegable japonés, para abrir en verano o exponer abierto en la pared",
                "Decoración mural ligera, para un salón o un despacho",
                "Accesorio de ceremonia, de baile o de disfraz",
            ]),
        },
    },
    "HNB-061": {
        "en": {
            "name": "Kitsune Mask",
            "blurb": "Hand-painted resin, silk cord, ready to hang",
            "usages": "\n".join([
                "Fox mask from Japanese festivals and matsuri, linked to yokai spirits",
                "Wall decoration to hang, or a mask to wear for a costume or cosplay",
                "Gift for a fan of anime, yokai or Japanese culture",
            ]),
        },
        "es": {
            "name": "Máscara Kitsune",
            "blurb": "Resina pintada a mano, cordón de seda, para colgar",
            "usages": "\n".join([
                "Máscara de zorro de las fiestas y los matsuri japoneses, ligada a los espíritus yokai",
                "Decoración mural para colgar, o máscara para llevar en un disfraz o un cosplay",
                "Regalo para un fan del anime, de los yokai o de la cultura japonesa",
            ]),
        },
    },
    "HNB-064": {
        "en": {
            "name": "Hannya Mask",
            "blurb": "Resin wall mask, gilded horns, 22 cm",
            "usages": "\n".join([
                "Demon mask from Noh theatre, a woman turned into a demon by jealousy",
                "Striking wall decoration for a living room, an office or a dojo",
                "For fans of Japanese theatre, traditional tattoos or martial arts",
            ]),
        },
        "es": {
            "name": "Máscara Hannya",
            "blurb": "Máscara mural de resina, cuernos dorados, 22 cm",
            "usages": "\n".join([
                "Máscara de demonio del teatro noh, una mujer convertida en demonio por los celos",
                "Decoración mural impactante para un salón, un despacho o un dojo",
                "Para aficionados al teatro japonés, al tatuaje tradicional o a las artes marciales",
            ]),
        },
    },
    "HNB-078": {
        "en": {
            "name": "Great Wave Print",
            "blurb": "After Hokusai, printed on washi paper, 30 × 40 cm",
            "usages": "\n".join([
                "Reproduction of Hokusai's ukiyo-e print, the great wave off Kanagawa",
                "Picture to frame, wall art for a living room, a bedroom or an office",
                "Gift for a lover of Japanese art, the sea or surfing",
            ]),
        },
        "es": {
            "name": "Estampa La Gran Ola",
            "blurb": "Según Hokusai, impresa en papel washi, 30 × 40 cm",
            "usages": "\n".join([
                "Reproducción de la estampa ukiyo-e de Hokusai, la gran ola de Kanagawa",
                "Cuadro para enmarcar, arte mural para un salón, un dormitorio o un despacho",
                "Regalo para un amante del arte japonés, del mar o del surf",
            ]),
        },
    },
    "HNB-021": {
        "en": {
            "name": "Torii LED Lamp",
            "blurb": "Torii night light, USB, three brightness levels",
            "usages": "\n".join([
                "Night light shaped like a torii, the gate of Shinto shrines",
                "Soft light for a bedroom, a bedside table or a desk",
                "USB powered, three brightness levels",
            ]),
        },
        "es": {
            "name": "Lámpara Torii LED",
            "blurb": "Luz nocturna torii, USB, tres intensidades",
            "usages": "\n".join([
                "Luz nocturna con forma de torii, el portal de los santuarios sintoístas",
                "Luz suave para un dormitorio, una mesita de noche o un escritorio",
                "Alimentada por USB, tres niveles de luz",
            ]),
        },
    },
    "HNB-026": {
        "en": {
            "name": "Moon Lamp",
            "blurb": "Moon lamp, 16 colors, remote control",
            "usages": "\n".join([
                "Full moon lamp, soft and colourful light",
                "Night light for a child's room or a bedside table, living room ambience",
                "Gift for a child, a teenager or an astronomy lover",
            ]),
        },
        "es": {
            "name": "Lámpara Luna",
            "blurb": "Lámpara luna, 16 colores, mando a distancia",
            "usages": "\n".join([
                "Lámpara con forma de luna llena, luz suave y de colores",
                "Luz nocturna para un cuarto infantil o una mesita de noche, ambiente de salón",
                "Regalo para un niño, un adolescente o un aficionado a la astronomía",
            ]),
        },
    },
    "HNB-083": {
        "en": {
            "name": "Ramen Lantern",
            "blurb": "Paper and bamboo chōchin, warm LED, 45 cm",
            "usages": "\n".join([
                "Chōchin lantern like those of ramen stalls and izakaya",
                "Warm ambient lighting for a living room, a kitchen, a bar or a balcony",
                "Decoration for a Japanese-themed evening or a restaurant",
            ]),
        },
        "es": {
            "name": "Farol Ramen",
            "blurb": "Chōchin de papel y bambú, LED cálido, 45 cm",
            "usages": "\n".join([
                "Farol chōchin como los de los puestos de ramen y las izakaya",
                "Iluminación ambiental cálida para un salón, una cocina, un bar o un balcón",
                "Decoración para una velada japonesa o un restaurante",
            ]),
        },
    },
}

def traductions(produit) -> dict[str, dict[str, str]]:
    """Traductions d'un produit, lues en base : {"en": {"name", "blurb", "usages", "alt"}}."""
    try:
        donnees = json.loads(produit.traductions or "{}")
    except (TypeError, ValueError):
        return {}
    if not isinstance(donnees, dict):
        return {}
    return {
        langue: {k: v for k, v in champs.items() if isinstance(v, str)}
        for langue, champs in donnees.items()
        if langue in LANGUES and isinstance(champs, dict)
    }


def localize(produit, lang: str | None) -> tuple[str, str, str]:
    """Nom, accroche et texte alternatif tels que la personne les lit.

    Champ par champ : langue demandée, puis anglais, puis français. Une fiche
    traduite à moitié reste lisible.
    """
    francais = {"name": produit.name, "blurb": produit.blurb, "alt": produit.alt or ""}
    if not lang or lang == "fr":
        return francais["name"], francais["blurb"], francais["alt"]
    tr = traductions(produit)
    ordre = [tr.get(lang, {}), tr.get("en", {}), francais]

    def champ(nom: str) -> str:
        return next((source[nom] for source in ordre if source.get(nom, "").strip()), "")

    return champ("name"), champ("blurb"), champ("alt")
