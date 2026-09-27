"""Déclinaisons d'un objet : une couleur, son prix, son stock, sa photo.

L'objet garde un prix et un stock, tirés de ses déclinaisons actives : le prix
le plus bas (« à partir de ») et la somme des stocks. Tout ce qui lit l'objet
(grille, recherche, conseiller, statistiques, entrepôt) continue ainsi de
fonctionner sans connaître les déclinaisons ; seuls le devis, la commande et
la fiche les lisent.
"""
from __future__ import annotations

import json

from . import models


def actives(p: models.Product) -> list[models.Variante]:
    return [v for v in p.variantes if v.active]


def synchroniser(p: models.Product) -> None:
    """Prix et stock de l'objet d'après ses déclinaisons actives ; sans elles, rien ne change."""
    vivantes = actives(p)
    if not vivantes:
        return
    p.price_cents = min(v.price_cents for v in vivantes)
    p.stock = sum(v.stock for v in vivantes)


def nom_de_ligne(article) -> str:
    """Nom d'une ligne de commande, déclinaison comprise : « Gourde isotherme (Noir) »."""
    libelle_fige = getattr(article, "variante_libelle", None)
    return f"{article.name} ({libelle_fige})" if libelle_fige else article.name


def libelle(v: models.Variante, lang: str | None) -> str:
    if lang and lang != "fr":
        try:
            traduit = json.loads(v.traductions or "{}").get(lang)
        except ValueError:
            traduit = None
        if traduit:
            return traduit
    return v.libelle
