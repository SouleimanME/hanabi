"""Contexte d'execution des migrations Alembic.

Deux ecarts par rapport au fichier genere par `alembic init` :

  - l'URL de connexion vient de la configuration de l'application, jamais de
    `alembic.ini`. Une chaine de connexion contient un mot de passe : la laisser
    dans un fichier versionne reviendrait a la publier ;
  - les modeles sont importes pour que `--autogenerate` compare le schema reel
    a ce que declare `models.py`.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# `app` doit etre importable : les migrations se lancent depuis `hanabi-back`.
from app import models  # noqa: F401  (enregistre les tables sur Base.metadata)
from app.database import DATABASE_URL, Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Renseignee ici plutot que dans alembic.ini, voir l'en-tete. Les `%` sont
# doubles car ConfigParser les interprete comme des marqueurs d'interpolation,
# et un mot de passe encode en pourcentage en contient.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genere le SQL sans se connecter, pour relecture ou application manuelle."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite ne sait pas modifier une colonne en place : Alembic recree la
        # table et recopie les donnees. Sans cela, toute migration touchant une
        # colonne existante echouerait sur la base de developpement.
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Applique les migrations sur une connexion ouverte."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            # Detecte aussi les changements de type, que la configuration par
            # defaut ignore.
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
