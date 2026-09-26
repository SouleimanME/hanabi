# -*- coding: utf-8 -*-
"""Comparaison des couples (thème, ton) rendus aux références étiquetées à la main.

Un couple attendu et rendu est juste. Un couple rendu hors attendu est faux,
sauf s'il est toléré. Un bon thème au mauvais ton compte donc un faux et un
manque : c'est le ton qui fait la valeur de l'analyse.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Score:
    justes: int = 0
    faux: int = 0
    manques: int = 0
    # Avis rendus exactement comme attendus (tolérés admis)
    avis_exacts: int = 0
    avis: int = 0

    @property
    def precision(self) -> float:
        return self.justes / (self.justes + self.faux) if self.justes + self.faux else 1.0

    @property
    def rappel(self) -> float:
        return self.justes / (self.justes + self.manques) if self.justes + self.manques else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.rappel
        return 2 * p * r / (p + r) if p + r else 0.0


def _couples(liste) -> set[tuple[str, str]]:
    return {(t, s) for t, s in liste or []}


def noter(reference: dict, rendu: list[tuple[str, str]], score: Score) -> dict:
    """Ajoute un avis au score et rend le détail de ses écarts."""
    attendu = _couples(reference.get("attendu"))
    tolere = _couples(reference.get("tolere"))
    rendus = _couples(rendu)
    justes = rendus & attendu
    faux = rendus - attendu - tolere
    manques = attendu - rendus
    score.justes += len(justes)
    score.faux += len(faux)
    score.manques += len(manques)
    score.avis += 1
    if not faux and not manques:
        score.avis_exacts += 1
    return {"faux": sorted(faux), "manques": sorted(manques)}
