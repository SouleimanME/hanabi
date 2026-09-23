# -*- coding: utf-8 -*-
"""Travail et calendrier : tout le graphe, chaque jour à 5 h UTC."""

from __future__ import annotations

import dagster as dg

# Hérite des partitions mensuelles de `externe/taux_change` ; les autres actifs
# se reconstruisent en entier
travail_entrepot = dg.define_asset_job(
    name="entrepot",
    selection=dg.AssetSelection.all(),
    description=(
        "Charge les sources externes puis reconstruit et teste les trois "
        "couches du médaillon."
    ),
)


@dg.schedule(
    job=travail_entrepot,
    cron_schedule="0 5 * * *",
    # Même heure que .github/workflows/entrepot.yml
    execution_timezone="UTC",
    default_status=dg.DefaultScheduleStatus.RUNNING,
)
def reconstruction_quotidienne(context: dg.ScheduleEvaluationContext):
    """Partition du mois en cours, rejouée chaque jour pour rattraper les cotations manquantes."""
    mois = context.scheduled_execution_time.strftime("%Y-%m-01")
    return dg.RunRequest(partition_key=mois)
