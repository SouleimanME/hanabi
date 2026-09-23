# -*- coding: utf-8 -*-
"""Traductions du nom et de l'accroche des produits.

Le français est en base. Repli : langue demandée, puis anglais, puis français.
"""

PRODUCT_I18N: dict[str, dict[str, dict[str, str]]] = {
    "HNB-052": {
        "en": {"name": "Kitsune Figure", "blurb": "Resin fox, hand-painted, 18 cm"},
        "es": {"name": "Figura Kitsune", "blurb": "Zorro de resina, pintado a mano, 18 cm"},
    },
    "HNB-018": {
        "en": {"name": "Golden Maneki-neko", "blurb": "Lucky cat, solar-powered waving arm"},
        "es": {"name": "Maneki-neko Dorado", "blurb": "Gato de la suerte, brazo solar motorizado"},
    },
    "HNB-067": {
        "en": {"name": "Red Daruma", "blurb": "Papier-mâché, eyes left to paint, 12 cm"},
        "es": {"name": "Daruma Rojo", "blurb": "Papel maché, ojos por pintar, 12 cm"},
    },
    "HNB-071": {
        "en": {"name": "Hana Kokeshi", "blurb": "Turned wood, hand-painted flowers, 10 cm"},
        "es": {"name": "Kokeshi Hana", "blurb": "Madera torneada, flores pintadas a mano, 10 cm"},
    },
    "HNB-074": {
        "en": {"name": "Ryū Dragon Figure", "blurb": "Lacquered resin dragon, crystal pearl, 15 cm"},
        "es": {"name": "Figura Ryū", "blurb": "Dragón de resina lacada, perla de cristal, 15 cm"},
    },
    "HNB-037": {
        "en": {"name": "Sensu Folding Fan", "blurb": "Bamboo and washi paper, wall stand included"},
        "es": {"name": "Abanico Sensu", "blurb": "Bambú y papel washi, soporte de pared incluido"},
    },
    "HNB-061": {
        "en": {"name": "Kitsune Mask", "blurb": "Hand-painted resin, silk cord, ready to hang"},
        "es": {"name": "Máscara Kitsune", "blurb": "Resina pintada a mano, cordón de seda, para colgar"},
    },
    "HNB-064": {
        "en": {"name": "Hannya Mask", "blurb": "Resin wall mask, gilded horns, 22 cm"},
        "es": {"name": "Máscara Hannya", "blurb": "Máscara mural de resina, cuernos dorados, 22 cm"},
    },
    "HNB-078": {
        "en": {"name": "Great Wave Print", "blurb": "After Hokusai, printed on washi paper, 30 × 40 cm"},
        "es": {"name": "Estampa La Gran Ola", "blurb": "Según Hokusai, impresa en papel washi, 30 × 40 cm"},
    },
    "HNB-021": {
        "en": {"name": "Torii LED Lamp", "blurb": "Torii night light, USB, three brightness levels"},
        "es": {"name": "Lámpara Torii LED", "blurb": "Luz nocturna torii, USB, tres intensidades"},
    },
    "HNB-026": {
        "en": {"name": "Moon Lamp", "blurb": "Moon lamp, 16 colors, remote control"},
        "es": {"name": "Lámpara Luna", "blurb": "Lámpara luna, 16 colores, mando a distancia"},
    },
    "HNB-083": {
        "en": {"name": "Ramen Lantern", "blurb": "Paper and bamboo chōchin, warm LED, 45 cm"},
        "es": {"name": "Farol Ramen", "blurb": "Chōchin de papel y bambú, LED cálido, 45 cm"},
    },
}


def localize(code: str, lang: str | None, name: str, blurb: str) -> tuple[str, str]:
    if not lang or lang == "fr":
        return name, blurb
    tr = PRODUCT_I18N.get(code, {})
    entry = tr.get(lang) or tr.get("en")
    if entry:
        return entry.get("name", name), entry.get("blurb", blurb)
    return name, blurb
