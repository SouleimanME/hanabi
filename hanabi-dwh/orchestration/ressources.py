# -*- coding: utf-8 -*-
"""Projet dbt et connexion, vus par Dagster.

Un seul point interessant ici : la connexion n'est pas redefinie. `dwh.py` sait
deja lire `DATABASE_URL` dans le `.env` de l'API et la decouper en variables
`DWH_*` que `profiles.yml` consomme ; ce module appelle ces deux fonctions
plutot que de recopier le decoupage. Une chaine de connexion definie a deux
endroits est une panne qui attend son heure - et celle-ci porte un mot de passe
echappe en pourcent, que le decoupage a la main oublie invariablement.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dagster_dbt import DbtCliResource, DbtProject

from dwh import RACINE, charge_env_api, executable_dbt, pose_variables_dbt

DBT = executable_dbt()

# Dagster lance ses serveurs de code par un chemin absolu, sans passer par un
# shell : `.venv/Scripts` n'est donc pas dans le PATH herite, et tout ce qui
# cherche `dbt` par son nom echoue sur un « dbt executable does not exist » qui
# ne dit pas ou regarder. La ressource ci-dessous recoit le chemin explicite,
# mais `prepare_if_dev()` fabrique en interne sa propre ressource avec le nom
# par defaut - d'ou cet ajout au PATH, qui couvre les deux.
if Path(DBT).is_absolute():
    os.environ["PATH"] = f"{Path(DBT).parent}{os.pathsep}{os.environ.get('PATH', '')}"

# Pose les variables `DWH_*` dans l'environnement du processus. `DbtCliResource`
# lance `dbt` en sous-processus et lui transmet cet environnement : c'est par
# la, et pas autrement, que le profil trouve ses identifiants.
#
# `obligatoire=False` : sans base joignable, on veut un graphe consultable et
# des executions qui echouent proprement, pas un serveur de code qui refuse de
# demarrer. C'est le meme parti que le workflow GitHub, inerte plutot que rouge
# tant que le secret n'est pas pose.
charge_env_api()
HOTE = pose_variables_dbt(obligatoire=False)

# Meme rappel que `dwh.py`, et pour la meme raison : reconstruire l'entrepot
# dans la base de production en croyant viser un conteneur local est l'erreur
# que cette ligne evite. L'hote seulement, jamais les identifiants. Une
# interface qui masque la base visee la rend plus facile a confondre qu'une
# ligne de commande, pas moins.
print(
    f"[dwh] base visee : {HOTE or 'aucune - graphe consultable, executions en echec'}",
    file=sys.stderr,
)

# `profiles_dir` pointe sur le projet et non sur `~/.dbt` : le profil est
# versionne avec les modeles, puisqu'il ne contient aucune valeur en dur.
PROJET = DbtProject(project_dir=RACINE, profiles_dir=RACINE)

# Dagster construit son graphe a partir de `target/manifest.json`, produit par
# `dbt parse`. En developpement il le regenere a chaque rechargement, ce qui
# evite un graphe qui decrit les modeles d'avant-hier. Ailleurs - integration
# continue, execution planifiee - le manifeste est genere par une etape
# explicite avant l'appel a Dagster, parce qu'un `parse` silencieux au
# demarrage d'un serveur de production est exactement ce qu'on ne veut pas.
PROJET.prepare_if_dev()

ressource_dbt = DbtCliResource(project_dir=PROJET, dbt_executable=DBT)
