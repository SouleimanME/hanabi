# -*- coding: utf-8 -*-
"""Un travail, un calendrier.

Le travail selectionne tout le graphe - les deux extractions et les 23 modeles
dbt - plutot que d'enumerer des etapes. C'est la difference de fond avec le
cron qu'il remplace : l'ordre n'est ecrit nulle part, il se deduit des
dependances declarees par les actifs. Ajouter une source demain ne demandera pas
de la placer avant `dbt build` dans un fichier YAML, ni de se souvenir qu'il
fallait le faire.
"""

from __future__ import annotations

import dagster as dg

# Le travail herite des partitions mensuelles de `externe/taux_change`, seul
# actif partitionne du graphe. Les autres sont construits en entier a chaque
# execution : une partition ne se propage pas aux actifs qui n'en declarent
# pas, et l'entrepot n'a pas de sens partiel - `gold_kpi_mensuel` se recalcule
# sur toute la serie ou pas du tout.
travail_entrepot = dg.define_asset_job(
    name="entrepot",
    selection=dg.AssetSelection.all(),
    description=(
        "Charge les sources externes puis reconstruit et teste les trois "
        "couches du medaillon."
    ),
)


@dg.schedule(
    job=travail_entrepot,
    cron_schedule="0 5 * * *",
    # Meme heure que le cron GitHub qu'il remplace : avant l'ouverture des
    # bureaux en France, hors des heures ou quelqu'un consulte le back-office.
    execution_timezone="UTC",
    default_status=dg.DefaultScheduleStatus.RUNNING,
)
def reconstruction_quotidienne(context: dg.ScheduleEvaluationContext):
    """Reconstruit chaque nuit, sur la partition du mois en cours.

    Rejouer le mois courant tous les jours peut surprendre - on ne recharge
    apparemment que quelques cotations nouvelles pour en redemander trente. Ce
    n'est pas du gaspillage mais du rattrapage : la BCE publie en fin de
    journee ouvree, et une execution manquee, un jour ferie de la BCE ou une
    revision de cotation se rattrapent d'eux-memes le lendemain. Un chargement
    strictement incremental laisserait ces trous derriere lui, et un trou dans
    une serie de taux ne se voit pas - il se lit comme un jour non cote.

    Les mois anterieurs ne sont pas concernes : ils se rattrapent depuis
    l'interface, en relancant les partitions manquantes.
    """
    mois = context.scheduled_execution_time.strftime("%Y-%m-01")
    return dg.RunRequest(partition_key=mois)
