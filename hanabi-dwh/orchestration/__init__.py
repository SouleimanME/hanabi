# -*- coding: utf-8 -*-
"""Orchestration de l'entrepôt par Dagster.

Même chaîne que `dwh.py build` et `python -m ingestion.sources tout`, déclarée
en graphe d'actifs : ordre déduit des dépendances, échecs limités à l'aval,
partitions mensuelles pour la série de taux, tests dbt en contrôles d'actifs,
et quatre contrôles de volume et de fraîcheur consignés en base.

Aucun daemon n'est déployé : en ligne, GitHub Actions déclenche ce travail.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `dwh.py` et `ingestion/` vivent un dossier au-dessus, et le répertoire courant
# du serveur de code Dagster n'est pas garanti
RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import dagster as dg  # noqa: E402

from .actifs_dbt import actifs_dbt, specs_sources_applicatives  # noqa: E402
from .actifs_externes import jours_feries, taux_change  # noqa: E402
from .controles import controles_volume_fraicheur  # noqa: E402
from .planification import reconstruction_quotidienne, travail_entrepot  # noqa: E402
from .ressources import ressource_dbt  # noqa: E402

# Les tables de `public` sont de simples descriptions : rien ne les matérialise
defs = dg.Definitions(
    assets=[actifs_dbt, taux_change, jours_feries, *specs_sources_applicatives()],
    asset_checks=[controles_volume_fraicheur],
    jobs=[travail_entrepot],
    schedules=[reconstruction_quotidienne],
    resources={"dbt": ressource_dbt},
)
