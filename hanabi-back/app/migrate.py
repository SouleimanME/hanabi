"""Migrations Alembic jouées au démarrage.

Le plan gratuit de Render n'a pas d'étape de déploiement séparée. Avec plusieurs
instances, il faudrait migrer dans une étape dédiée.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from .config import settings
from .database import base_locale, engine

log = logging.getLogger("hanabi.migrate")

# Racine du backend, où vit alembic.ini
RACINE = Path(__file__).resolve().parent.parent


def _config() -> Config:
    cfg = Config(str(RACINE / "alembic.ini"))
    # Chemin absolu, indépendant du répertoire courant
    cfg.set_main_option("script_location", str(RACINE / "migrations"))
    # Les journaux d'alembic.ini désactiveraient tous ceux de l'application
    cfg.attributes["configure_logger"] = False
    return cfg


def _base_anterieure_a_alembic(cx) -> bool:
    """Base créée par l'ancien `create_all` : tables présentes, sans `alembic_version`."""
    tables = set(inspect(cx).get_table_names())
    return "users" in tables and "alembic_version" not in tables


def _verifie_droit_de_migrer(url, actuelle: str | None, tete: str) -> None:
    """Hors production, seule une base locale se migre.

    Un poste dont le .env vise la base de production la migrerait en avance sur
    le code déployé, qui ne reconnaîtrait plus la révision et ne redémarrerait plus.
    """
    if settings.is_prod or settings.MIGRER_BASE_DISTANTE or base_locale(url):
        return
    raise RuntimeError(
        f"Migration refusée : la base {url.host} est distante et ENV n'est pas « prod » "
        f"(révision {actuelle or 'aucune'}, le code attend {tete}). "
        "Vise une base locale, ou pose MIGRER_BASE_DISTANTE=1 pour la migrer à dessein."
    )


def run_migrations() -> None:
    cfg = _config()
    tete = ScriptDirectory.from_config(cfg).get_current_head()

    with engine.begin() as cx:
        actuelle = MigrationContext.configure(cx).get_current_revision()
        if actuelle == tete:
            return
        _verifie_droit_de_migrer(engine.url, actuelle, tete)

        # Alembic passe par cette connexion, pas par l'URL de env.py
        cfg.attributes["connection"] = cx
        if _base_anterieure_a_alembic(cx):
            command.stamp(cfg, "head")
            log.warning(
                "Base antérieure aux migrations : marquée à jour sans exécution. "
                "Elle peut manquer les index ajoutés depuis ; en développement, "
                "supprimer le fichier et relancer donne un schéma propre."
            )
            return

        command.upgrade(cfg, "head")
