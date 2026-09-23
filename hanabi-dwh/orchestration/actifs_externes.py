# -*- coding: utf-8 -*-
"""Les deux sources externes, en amont du graphe dbt.

Réutilise `ingestion/sources.py`. Le taux de change est partitionné par mois
(un appel par mois, rattrapage ciblé, upsert sans doublon) ; les jours fériés,
publiés d'un bloc par année, se rechargent en entier.
"""

import datetime as dt

import dagster as dg

# Import direct, sans `from __future__ import annotations` (voir actifs_dbt.py)
from dagster import AssetExecutionContext

from ingestion.sources import (
    DEBUT_TAUX,
    DEVISE,
    PAYS,
    PREMIERE_ANNEE_FERIES,
    accorde_lecture,
    charge_feries,
    charge_taux,
    ouvre_base,
)

GROUPE_EXTERNE = "sources_externes"

# `end_offset=1` inclut le mois en cours, sinon la série s'arrêterait au dernier mois clos
PARTITIONS_MOIS = dg.MonthlyPartitionsDefinition(start_date=DEBUT_TAUX, end_offset=1)


@dg.asset(
    key=["externe", "taux_change"],
    group_name=GROUPE_EXTERNE,
    partitions_def=PARTITIONS_MOIS,
    kinds={"python", "postgres"},
    description=(
        "Taux de référence EUR vers JPY publiés par Frankfurter (BCE). Le coût "
        "fournisseur est en yen et la marge en euros : la série sépare l'effet "
        "du prix de celui du change."
    ),
)
def taux_change(context: AssetExecutionContext) -> dg.MaterializeResult:
    fenetre = context.partition_time_window
    debut = fenetre.start.date()

    # Borne haute exclusive, et jamais au-delà d'aujourd'hui
    fin = min(fenetre.end.date() - dt.timedelta(days=1), dt.date.today())
    if fin < debut:
        return dg.MaterializeResult(
            metadata={"cotations": 0, "note": "partition entierement future"}
        )

    with ouvre_base() as cx:
        ecrites = charge_taux(cx, debut, fin)
        accorde_lecture(cx)

    # Lignes écrites, pas lignes reçues
    return dg.MaterializeResult(
        metadata={
            "cotations": ecrites,
            "devise": DEVISE,
            "debut": str(debut),
            "fin": str(fin),
        }
    )


@dg.asset(
    key=["externe", "jours_feries"],
    group_name=GROUPE_EXTERNE,
    kinds={"python", "postgres"},
    description=(
        "Jours fériés français et japonais (Nager.Date). Côté France, ils déplacent "
        "la demande ; côté Japon (Golden Week, Obon), ils allongent le réassort."
    ),
)
def jours_feries() -> dg.MaterializeResult:
    # Année suivante incluse : les calendriers sont publiés à l'avance
    de = PREMIERE_ANNEE_FERIES
    a = dt.date.today().year + 1

    with ouvre_base() as cx:
        ecrits = charge_feries(cx, de, a)
        accorde_lecture(cx)

    return dg.MaterializeResult(
        metadata={
            "jours": ecrits,
            "pays": ", ".join(PAYS),
            "annees": f"{de} a {a}",
        }
    )
