"""Comparaison d'un résultat à celui d'une requête de référence.

Juste quand, pour chaque colonne de la référence, le résultat en a une aux
mêmes valeurs, sur autant de lignes. Les noms de colonnes et les colonnes en
plus ne comptent pas : « quel mois » peut rendre le mois et son chiffre.
L'ordre ne compte que si la question l'exige.
"""
from decimal import Decimal


def _normaliser(valeur):
    if isinstance(valeur, (int, float, Decimal)) and not isinstance(valeur, bool):
        return round(float(valeur), 2)
    return valeur


def _colonnes(resultat: dict) -> list[list]:
    lignes = resultat["lignes"]
    largeur = len(resultat["colonnes"])
    return [[_normaliser(ligne[i]) for ligne in lignes] for i in range(largeur)]


def meme_reponse(reference: dict, candidat: dict, ordonne: bool = False) -> bool:
    if len(reference["lignes"]) != len(candidat["lignes"]):
        return False
    cle = (lambda valeurs: valeurs) if ordonne else (lambda valeurs: sorted(valeurs, key=repr))
    disponibles = [cle(c) for c in _colonnes(candidat)]
    for colonne in _colonnes(reference):
        cherchee = cle(colonne)
        if cherchee not in disponibles:
            return False
        disponibles.remove(cherchee)
    return True
