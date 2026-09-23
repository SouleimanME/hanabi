# -*- coding: utf-8 -*-
"""Les 27 modèles dbt exposés comme actifs Dagster.

Dagster lance `dbt build` et lit son flux d'événements : le graphe montre les
modèles réels, leurs durées et leurs tests.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import dagster as dg

# Import direct, et pas de `from __future__ import annotations` dans ce module :
# Dagster compare l'annotation de `context` au type réel.
from dagster import AssetExecutionContext
from dagster_dbt import (
    DagsterDbtTranslator,
    DagsterDbtTranslatorSettings,
    DbtCliResource,
    dbt_assets,
)

from .actifs_externes import GROUPE_EXTERNE
from .ressources import PROJET

# Tables de `public`, écrites par l'API et seulement lues par la chaîne
GROUPE_APPLICATION = "ecrit_par_l_api"


class TraducteurHanabi(DagsterDbtTranslator):
    """Correspondance entre le vocabulaire de dbt et celui de Dagster."""

    def get_asset_key(self, props: Mapping[str, Any]) -> dg.AssetKey:
        """Nomme les sources d'après leur schéma PostgreSQL (`public`, `externe`).

        Les actifs d'ingestion portent `externe/taux_change` et
        `externe/jours_feries` : une autre clé couperait le graphe en deux.
        """
        if props["resource_type"] == "source":
            return dg.AssetKey([props["schema"], props["name"]])
        return super().get_asset_key(props)

    def get_group_name(self, props: Mapping[str, Any]) -> str | None:
        """Groupe par couche (`config.schema`, posé par dbt_project.yml) ; les sources à part."""
        if props["resource_type"] == "source":
            return (
                GROUPE_APPLICATION if props["schema"] == "public" else GROUPE_EXTERNE
            )
        couche = (props.get("config") or {}).get("schema")
        return couche or super().get_group_name(props)


# 95 des 111 assertions deviennent des contrôles d'actifs ; les 16 autres (sources
# et tests singuliers) restent jouées par `dbt build` sans actif de rattachement.
TRADUCTEUR = TraducteurHanabi(
    settings=DagsterDbtTranslatorSettings(enable_asset_checks=True)
)


def specs_sources_applicatives() -> list[dg.AssetSpec]:
    """Déclare les tables de `public` comme actifs externes, avec clé et groupe du traducteur.

    `@dbt_assets` ne crée d'actifs que pour les modèles ; les sources de `externe`
    sont déjà produites par les actifs d'ingestion.
    """
    manifeste = json.loads(Path(PROJET.manifest_path).read_text(encoding="utf-8"))
    return [
        dg.AssetSpec(
            key=TRADUCTEUR.get_asset_key(props),
            group_name=TRADUCTEUR.get_group_name(props),
            description=props.get("description") or None,
            kinds={"postgres"},
        )
        for props in manifeste["sources"].values()
        if props["schema"] == "public"
    ]


@dbt_assets(
    manifest=PROJET.manifest_path,
    dagster_dbt_translator=TRADUCTEUR,
    name="entrepot_dbt",
)
def actifs_dbt(context: AssetExecutionContext, dbt: DbtCliResource):
    """`build` : construit et teste dans l'ordre du graphe ; un test en échec bloque l'aval."""
    yield from dbt.cli(["build"], context=context).stream()
