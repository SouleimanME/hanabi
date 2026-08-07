# -*- coding: utf-8 -*-
"""Traductions du contenu produit (nom + description).

Le francais est la source en base. On surcharge ici pour en/es.
Pour ajouter une langue : ajoute une clef (ex "de") dans chaque produit.
Chaine de repli cote API : langue demandee -> en -> francais (base).
"""

PRODUCT_I18N: dict[str, dict[str, dict[str, str]]] = {
    "HNB-014": {
        "en": {"name": "Maneki-neko Cat Collar", "blurb": "Cat collar, brass bell, soft leather"},
        "es": {"name": "Collar Maneki-neko", "blurb": "Collar para gato, cascabel de latón, cuero suave"},
    },
    "HNB-021": {
        "en": {"name": "Torii LED Lamp", "blurb": "Torii night light, USB, three brightness levels"},
        "es": {"name": "Lámpara Torii LED", "blurb": "Luz nocturna torii, USB, tres intensidades"},
    },
    "HNB-008": {
        "en": {"name": "Sushi Bandana", "blurb": "Dog bandana, cotton, adjustable size"},
        "es": {"name": "Bandana Sushi", "blurb": "Bandana para perro, algodón, talla ajustable"},
    },
    "HNB-015": {
        "en": {"name": "Sakura Bowl", "blurb": "Ceramic pet bowl, cherry blossom pattern"},
        "es": {"name": "Comedero Sakura", "blurb": "Comedero de cerámica, motivo flor de cerezo"},
    },
    "HNB-033": {
        "en": {"name": "Lacquered Chopsticks", "blurb": "Pair, urushi lacquer, chopstick rest included"},
        "es": {"name": "Palillos Lacados", "blurb": "Par, laca urushi, reposa-palillos incluido"},
    },
    "HNB-037": {
        "en": {"name": "Sensu Folding Fan", "blurb": "Folding fan, bamboo and washi paper"},
        "es": {"name": "Abanico Sensu", "blurb": "Abanico plegable, bambú y papel washi"},
    },
    "HNB-041": {
        "en": {"name": "Ramen Bowl", "blurb": "Ceramic, 1 L, seigaiha wave pattern"},
        "es": {"name": "Bol de Ramen", "blurb": "Cerámica, 1 L, motivo de olas seigaiha"},
    },
    "HNB-009": {
        "en": {"name": "Neko Futon Bed", "blurb": "Cat bed, quilted cotton futon"},
        "es": {"name": "Futón Néko", "blurb": "Cama para gato, futón de algodón acolchado"},
    },
    "HNB-052": {
        "en": {"name": "Kitsune Figure", "blurb": "Resin fox, hand-painted, 18 cm"},
        "es": {"name": "Figura Kitsune", "blurb": "Zorro de resina, pintado a mano, 18 cm"},
    },
    "HNB-045": {
        "en": {"name": "Seigaiha Tenugui", "blurb": "Cotton cloth, traditional dyeing"},
        "es": {"name": "Tenugui Seigaiha", "blurb": "Paño de algodón, teñido tradicional"},
    },
    "HNB-026": {
        "en": {"name": "Moon Lamp", "blurb": "Moon lamp, 16 colors, remote control"},
        "es": {"name": "Lámpara Luna", "blurb": "Lámpara luna, 16 colores, mando a distancia"},
    },
    "HNB-018": {
        "en": {"name": "Golden Maneki-neko", "blurb": "Lucky cat, solar-powered waving arm"},
        "es": {"name": "Maneki-neko Dorado", "blurb": "Gato de la suerte, brazo solar motorizado"},
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
