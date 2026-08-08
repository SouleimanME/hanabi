# -*- coding: utf-8 -*-
"""Les 27 modeles dbt, exposes un par un comme actifs Dagster.

`dbt build` reste la commande executee : Dagster ne reimplemente pas dbt, il le
lance et lit son flux d'evenements pour savoir quel modele vient d'etre
construit, en combien de temps, et quels tests ont porte dessus. Le graphe
affiche donc les modeles reels et non une boite noire nommee « entrepot ».

Deux traductions valent d'etre expliquees, elles vivent dans `TraducteurHanabi`
ci-dessous : le nommage des sources et le regroupement par couche. Une
troisieme chose se joue dans `specs_sources_applicatives`, qui rattache le
graphe aux tables que l'API ecrit.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import dagster as dg

# Dagster compare l'annotation de `context` au type reel pour decider quoi
# passer a la fonction. Deux consequences, qui expliquent ce que ce fichier a
# d'inhabituel : la classe s'importe nue plutot que via `dg`, et
# `from __future__ import annotations` est absent de ce module - il
# transformerait toutes les annotations en chaines, et la comparaison
# echouerait sur un message qui donne l'impression d'annoter le bon type.
from dagster import AssetExecutionContext
from dagster_dbt import (
    DagsterDbtTranslator,
    DagsterDbtTranslatorSettings,
    DbtCliResource,
    dbt_assets,
)

from .actifs_externes import GROUPE_EXTERNE
from .ressources import PROJET

# Les tables de `public`. Elles apparaissent dans le graphe parce que bronze les
# declare en source, mais rien ici ne les produit : c'est l'API qui les ecrit.
# Les nommer d'apres leur producteur plutot que d'apres leur schema evite la
# lecture la plus couteuse du graphe - croire que la chaine pourrait les
# reconstruire.
GROUPE_APPLICATION = "ecrit_par_l_api"


class TraducteurHanabi(DagsterDbtTranslator):
    """Correspondance entre le vocabulaire de dbt et celui de Dagster."""

    def get_asset_key(self, props: Mapping[str, Any]) -> dg.AssetKey:
        """Nomme les sources d'apres leur schema PostgreSQL.

        Par defaut, dagster-dbt nomme une source d'apres son groupe declare -
        ici `hanabi_oltp` et `hanabi_externe`, qui n'existent que dans
        `sources.yml`. Le schema, lui, existe vraiment dans la base : c'est
        `public` que l'API ecrit, et `externe` ou atterrissent les extractions.

        L'enjeu n'est pas cosmetique. Les actifs Python de `actifs_externes.py`
        portent les clefs `externe/taux_change` et `externe/jours_feries` ; si
        la source dbt s'appelait autrement, les deux moities du graphe
        resteraient cote a cote sans jamais se rejoindre, et l'extraction ne
        serait pas une dependance de bronze mais un travail voisin, lance a
        cote et jamais avant.
        """
        if props["resource_type"] == "source":
            return dg.AssetKey([props["schema"], props["name"]])
        return super().get_asset_key(props)

    def get_group_name(self, props: Mapping[str, Any]) -> str | None:
        """Regroupe les modeles par couche du medaillon.

        `config.schema` vaut `bronze`, `silver` ou `gold` - c'est
        `dbt_project.yml` qui le pose, par dossier. Reprendre ce champ plutot
        que de redecouper le chemin du fichier garantit que le regroupement
        affiche est celui qui sera reellement ecrit dans la base.

        Les sources ne portent pas de `config.schema` et tomberaient sinon dans
        un groupe « default » qui melangerait les tables de l'application et
        les extractions - or c'est precisement leur difference qui compte : les
        premieres, la chaine ne fait que les lire.
        """
        if props["resource_type"] == "source":
            return (
                GROUPE_APPLICATION if props["schema"] == "public" else GROUPE_EXTERNE
            )
        couche = (props.get("config") or {}).get("schema")
        return couche or super().get_group_name(props)


# `enable_asset_checks` est le defaut, mais il porte ici l'essentiel de
# l'interet : 96 des 112 assertions dbt deviennent des controles d'actifs. Un
# test qui echoue se lit alors sur le modele concerne dans l'interface, au lieu
# de se chercher dans mille lignes de journal - et l'historique repond a
# « depuis quand ce test echoue-t-il ? », qui est la vraie question.
#
# Les 16 restantes - 14 portant sur une source, 2 tests singuliers qui
# reconcilient plusieurs modeles a la fois - n'ont pas d'actif unique auquel se
# rattacher. Elles continuent d'etre jouees par `dbt build` et de bloquer la
# construction ; elles ne s'affichent simplement pas comme controles.
TRADUCTEUR = TraducteurHanabi(
    settings=DagsterDbtTranslatorSettings(enable_asset_checks=True)
)


def specs_sources_applicatives() -> list[dg.AssetSpec]:
    """Declare les tables de `public` comme actifs externes.

    Sans cette fonction elles apparaitraient quand meme - Dagster fabrique un
    actif pour toute dependance qu'aucune definition ne couvre - mais sans
    groupe ni description, melangees aux extractions dans un fourre-tout
    « default ». Or c'est precisement leur difference qui compte : celles-la, la
    chaine ne fait que les lire.

    dagster-dbt ne les produit pas lui-meme. `@dbt_assets` ne cree des actifs
    que pour les ressources selectionnees - les modeles - et se contente de
    citer les sources en dependance ; le traducteur n'est donc jamais consulte a
    leur sujet. On l'appelle ici explicitement, pour que la clef et le groupe
    suivent la meme regle que partout ailleurs plutot qu'une seconde ecrite a
    cote.

    Les sources du schema `externe` sont exclues : leurs clefs sont deja portees
    par les actifs d'ingestion, qui eux savent les produire.
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
    """`build` et non `run` : construit ET teste, dans l'ordre du graphe.

    Un modele dont un test echoue bloque ce qui en depend, plutot que de
    propager une donnee fausse jusqu'au tableau de bord. C'est la meme raison
    qui faisait choisir `build` dans le workflow GitHub ; elle n'a pas change en
    passant sous Dagster, et il aurait ete tentant de la perdre en decoupant
    construction et tests en deux etapes que l'interface aurait affichees plus
    joliment.
    """
    yield from dbt.cli(["build"], context=context).stream()
