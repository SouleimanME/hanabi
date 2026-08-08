# -*- coding: utf-8 -*-
"""Orchestration de l'entrepot par Dagster.

CE QUE CE PAQUET AJOUTE, ET CE QU'IL NE CHANGE PAS

Il ne change ni un modele dbt, ni une ligne d'extraction. `dwh.py build` et
`python -m ingestion.sources tout` fonctionnent exactement comme avant, et
restent le chemin le plus court pour construire l'entrepot sur un poste. Ce
paquet declare la meme chaine sous forme de graphe d'actifs.

Ce que le cron ne savait pas faire :

- **L'ordre etait ecrit a la main.** Le workflow lancait l'extraction, puis
  `dbt build`, parce que quelqu'un l'avait ecrit dans cet ordre. Ici bronze
  depend de `externe/taux_change` parce que le modele le declare, et
  l'ordonnancement se deduit du graphe. Une source ajoutee demain se place
  toute seule.

- **Un echec etait binaire.** Une extraction qui tombe faisait echouer la
  tache entiere, y compris la reconstruction de modeles qui n'avaient aucun
  besoin de cette source. Dagster n'arrete que l'aval du noeud en echec.

- **Rien ne se rattrapait.** La serie de taux est desormais partitionnee par
  mois : Dagster sait quels mois sont charges, et relancer un mois manquant
  est une action, pas un script a retrouver. L'upsert etait deja idempotent -
  c'est ce qui rend le rattrapage sur.

- **Les 112 tests dbt se lisaient dans un journal.** Ils deviennent des
  controles d'actifs, attaches au modele qu'ils verifient, avec leur
  historique.

CE QUI RESTE VOLONTAIREMENT DEHORS

Aucun daemon Dagster n'est deploye. Le calendrier declare ici s'execute quand
`dagster dev` tourne ; en ligne, c'est toujours GitHub Actions qui declenche,
mais en appelant ce travail plutot qu'en redisant les etapes. La planification
vit donc a deux endroits, l'enchainement a un seul - et c'est l'enchainement
qui se serait desynchronise.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `dwh.py` et le paquet `ingestion/` vivent a la racine du projet dbt, un
# dossier au-dessus de celui-ci. Dagster importe ce paquet depuis son propre
# serveur de code, dont le repertoire courant n'est pas garanti : sans cette
# ligne, l'import fonctionnerait depuis `hanabi-dwh/` et nulle part ailleurs.
# L'alternative etait d'empaqueter le projet dbt et de l'installer en editable,
# soit un `pyproject.toml` complet et une etape d'installation de plus pour
# trois imports.
RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import dagster as dg  # noqa: E402

from .actifs_dbt import actifs_dbt, specs_sources_applicatives  # noqa: E402
from .actifs_externes import jours_feries, taux_change  # noqa: E402
from .planification import reconstruction_quotidienne, travail_entrepot  # noqa: E402
from .ressources import ressource_dbt  # noqa: E402

# Les tables de `public` figurent dans la liste, mais comme simples
# descriptions : aucune fonction ne les produit, parce que c'est l'API qui les
# ecrit. Le graphe commence donc a l'application, sans qu'on ait a lui mentir
# sur qui la remplit - et `AssetSelection.all()` ne les retient pas, un actif
# sans calcul n'etant pas materialisable.
defs = dg.Definitions(
    assets=[actifs_dbt, taux_change, jours_feries, *specs_sources_applicatives()],
    jobs=[travail_entrepot],
    schedules=[reconstruction_quotidienne],
    resources={"dbt": ressource_dbt},
)
