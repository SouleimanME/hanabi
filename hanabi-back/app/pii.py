"""Masquage des données personnelles pour le compte back-office de démonstration.

Ses identifiants sont publics : toute route du back-office qui rend un nom, une
adresse e-mail ou une ville la masque pour lui, côté serveur, pas seulement dans
l'interface. La forme reste reconnaissable (domaine de l'e-mail, prénom) pour
que les écrans gardent leur sens.
"""
from __future__ import annotations

from datetime import date


def masquer_email(adresse: str | None) -> str:
    """`marie.durand@exemple.fr` devient `m***d@exemple.fr` ; le domaine reste."""
    if not adresse:
        return "***"
    nom, _, domaine = adresse.partition("@")
    if not domaine:
        return "***"
    if len(nom) <= 2:
        return f"{nom[:1]}***@{domaine}"
    return f"{nom[0]}***{nom[-1]}@{domaine}"


def masquer_nom(nom: str | None) -> str:
    """`Marie Durand` devient `Marie D.`."""
    if not nom:
        return "***"
    morceaux = nom.strip().split()
    if not morceaux:
        return "***"
    if len(morceaux) == 1:
        return morceaux[0]
    return f"{morceaux[0]} {morceaux[-1][:1]}."


def masquer_ville(ville: str | None) -> str | None:
    """Ville entièrement masquée : croisée au prénom, elle identifie."""
    return None if ville is None else "***"


def masquer_date_naissance(_valeur: date | None) -> None:
    """Toujours absente."""
    return None


def masquer_adresse(valeur: str | None) -> str | None:
    """Adresse postale ou code postal, entièrement masqués."""
    return None if valeur is None else "***"


# Clés d'une ligne qui désignent une personne, et leur masque
_MASQUES = {
    "name": masquer_nom,
    "email": masquer_email,
    "city": masquer_ville,
    "ship_name": masquer_nom,
    "ship_addr": masquer_adresse,
    "ship_cp": masquer_adresse,
    "ship_city": masquer_ville,
}


def masquer_personne(ligne: dict | None) -> dict | None:
    """Copie de la ligne, champs personnels masqués. À n'appeler que sur une ligne qui décrit une personne."""
    if ligne is None:
        return None
    return {
        cle: (_MASQUES[cle](valeur) if cle in _MASQUES else valeur)
        for cle, valeur in ligne.items()
    }
