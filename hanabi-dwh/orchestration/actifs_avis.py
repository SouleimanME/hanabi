# -*- coding: utf-8 -*-
"""Thèmes et tons des avis, lus par un modèle de langue, en amont de dbt.

Réutilise `ingestion/avis.py`. Seuls les textes jamais lus avec la consigne
actuelle partent chez le fournisseur : une exécution quotidienne ne coûte que
les nouveaux avis. Une panne du fournisseur ne bloque pas l'entrepôt ; elle
s'affiche en avertissement et le passage suivant reprend où il s'est arrêté.
"""

import dagster as dg

# Import direct, sans `from __future__ import annotations` (voir actifs_dbt.py)
from dagster import AssetExecutionContext

from ingestion.avis import LIMITE_DEFAUT, enrichir
from ingestion.sources import accorde_lecture, ouvre_base


class ConfigAvis(dg.Config):
    # Plafond de textes lus par exécution
    limite: int = LIMITE_DEFAUT


@dg.asset(
    key=["externe", "analyses_avis"],
    group_name="enrichissement",
    deps=[dg.AssetKey(["public", "reviews"])],
    kinds={"python", "postgres"},
    description=(
        "Pour chaque texte d'avis, les aspects dont il parle (livraison, finition, "
        "taille...) et leur ton, lus par un modèle de langue dans une liste fermée. "
        "La note dit qu'un client est déçu ; ces thèmes disent de quoi."
    ),
)
def analyses_avis(context: AssetExecutionContext, config: ConfigAvis) -> dg.MaterializeResult:
    with ouvre_base() as cx:
        bilan = enrichir(cx, config.limite)
        accorde_lecture(cx)
    if "note" in bilan:
        context.log.info(f"Avis non analysés : {bilan['note']}.")
    if "erreur" in bilan:
        context.log.warning(f"Analyse interrompue : {bilan['erreur']}. Reprise au prochain passage.")
    return dg.MaterializeResult(metadata=bilan)
