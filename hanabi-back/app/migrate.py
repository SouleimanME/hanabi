"""Application des migrations au demarrage du service.

L'hebergeur ne fournit pas d'etape de deploiement separee sur le plan gratuit :
il construit l'image puis lance la commande de demarrage, sans crochet ou l'on
pourrait glisser un `alembic upgrade head`. La migration se joue donc au
lancement de l'application, avant qu'elle n'accepte la moindre requete.

Ce n'est pas ce qu'on ferait sur une infrastructure a plusieurs instances : deux
processus demarrant ensemble tenteraient de migrer en meme temps. PostgreSQL
serialise les verrous sur `alembic_version`, si bien que le second attend puis
ne trouve rien a faire, mais cela reste une propriete du moteur plutot qu'une
garantie de l'application. Avec un seul processus web, la question ne se pose
pas ; elle se poserait des la deuxieme instance, et c'est alors une etape de
deploiement dediee qu'il faudrait.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .database import engine

log = logging.getLogger("hanabi.migrate")

# `alembic.ini` vit a la racine du projet backend, un cran au-dessus du paquet.
RACINE = Path(__file__).resolve().parent.parent


def _config() -> Config:
    cfg = Config(str(RACINE / "alembic.ini"))
    # Chemin absolu : Alembic resout `script_location` par rapport au repertoire
    # courant, qui n'est pas forcement celui du projet selon la facon dont le
    # service est lance.
    cfg.set_main_option("script_location", str(RACINE / "migrations"))
    return cfg


def _base_anterieure_a_alembic() -> bool:
    """Detecte une base creee par l'ancien `create_all`.

    Reconnaissable a ceci : les tables metier existent, mais la table de suivi
    des revisions n'a jamais ete creee. Rejouer la migration initiale sur une
    telle base echouerait sur un « table already exists ».
    """
    tables = set(inspect(engine).get_table_names())
    return "users" in tables and "alembic_version" not in tables


def run_migrations() -> None:
    cfg = _config()

    if _base_anterieure_a_alembic():
        # On enregistre la base comme etant a jour sans rien executer.
        command.stamp(cfg, "head")
        log.warning(
            "Base anterieure aux migrations : marquee a jour sans execution. "
            "Elle peut manquer les index ajoutes depuis ; en developpement, "
            "supprimer le fichier et relancer donne un schema propre."
        )
        return

    command.upgrade(cfg, "head")
