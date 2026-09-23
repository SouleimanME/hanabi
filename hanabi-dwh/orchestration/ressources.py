# -*- coding: utf-8 -*-
"""Projet dbt et connexion pour Dagster, en réutilisant le découpage de `dwh.py`."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dagster_dbt import DbtCliResource, DbtProject

from dwh import RACINE, charge_env_api, executable_dbt, pose_variables_dbt

DBT = executable_dbt()

# Dagster lance ses serveurs sans shell : le venv n'est pas dans le PATH, et
# `prepare_if_dev()` cherche `dbt` par son nom
if Path(DBT).is_absolute():
    os.environ["PATH"] = f"{Path(DBT).parent}{os.pathsep}{os.environ.get('PATH', '')}"

# Variables `DWH_*` transmises au sous-processus dbt. Sans base joignable, le
# graphe reste consultable et les exécutions échouent.
charge_env_api()
HOTE = pose_variables_dbt(obligatoire=False)

# Hôte visé affiché, jamais les identifiants
print(
    f"[dwh] base visée : {HOTE or 'aucune (graphe consultable, exécutions en échec)'}",
    file=sys.stderr,
)

# Profil versionné avec le projet, sans valeur en dur
PROJET = DbtProject(project_dir=RACINE, profiles_dir=RACINE)

# Régénère le manifeste en développement ; en CI et en planifié, `dbt parse` le fait avant
PROJET.prepare_if_dev()

ressource_dbt = DbtCliResource(project_dir=PROJET, dbt_executable=DBT)
