"""Migrations Alembic jouées au démarrage.

Le plan gratuit de Render n'a pas d'étape de déploiement séparée. Avec plusieurs
instances, il faudrait migrer dans une étape dédiée.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .database import engine

log = logging.getLogger("hanabi.migrate")

# Racine du backend, où vit alembic.ini
RACINE = Path(__file__).resolve().parent.parent


def _config() -> Config:
    cfg = Config(str(RACINE / "alembic.ini"))
    # Chemin absolu, indépendant du répertoire courant
    cfg.set_main_option("script_location", str(RACINE / "migrations"))
    return cfg


def _base_anterieure_a_alembic() -> bool:
    """Base créée par l'ancien `create_all` : tables présentes, sans `alembic_version`."""
    tables = set(inspect(engine).get_table_names())
    return "users" in tables and "alembic_version" not in tables


def run_migrations() -> None:
    cfg = _config()

    if _base_anterieure_a_alembic():
        command.stamp(cfg, "head")
        log.warning(
            "Base antérieure aux migrations : marquée à jour sans exécution. "
            "Elle peut manquer les index ajoutés depuis ; en développement, "
            "supprimer le fichier et relancer donne un schéma propre."
        )
        return

    command.upgrade(cfg, "head")
