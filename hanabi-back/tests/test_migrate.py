"""Démarrage : les migrations ne touchent qu'une base qu'elles ont le droit de modifier."""
import logging

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app import migrate
from app.config import settings
from app.database import base_locale

_SCRIPTS = ScriptDirectory.from_config(migrate._config())
TETE = _SCRIPTS.get_current_head()
PRECEDENTE = _SCRIPTS.get_revision(TETE).down_revision


def _revision(moteur):
    with moteur.connect() as cx:
        return MigrationContext.configure(cx).get_current_revision()


def _amener(moteur, revision):
    cfg = Config()
    cfg.set_main_option("script_location", str(migrate.RACINE / "migrations"))
    with moteur.begin() as cx:
        cfg.attributes["connection"] = cx
        command.upgrade(cfg, revision)


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Base une révision derrière le code, branchée à la place de celle de l'application."""
    moteur = create_engine(f"sqlite:///{tmp_path / 'demarrage.db'}")
    _amener(moteur, PRECEDENTE)
    monkeypatch.setattr(migrate, "engine", moteur)
    yield moteur
    moteur.dispose()


@pytest.fixture
def distante(monkeypatch):
    """La base est vue comme hébergée ailleurs, à la manière de Neon."""
    monkeypatch.setattr(migrate, "base_locale", lambda url: False)


@pytest.mark.parametrize(
    "url, locale",
    [
        ("sqlite:///./atelier.db", True),
        ("sqlite://", True),
        ("postgresql+psycopg://postgres:hanabi@localhost:5433/hanabi", True),
        ("postgresql+psycopg://postgres:hanabi@127.0.0.1:5432/hanabi", True),
        ("postgresql+psycopg://postgres@/hanabi", True),
        ("postgresql+psycopg://u:p@ep-calme-lac-123456.eu-central-1.aws.neon.tech/hanabi", False),
        ("postgresql+psycopg://u:p@db.interne:5432/hanabi", False),
    ],
)
def test_base_locale(url, locale):
    assert base_locale(url) is locale


class TestGardeFou:
    def test_une_base_distante_n_est_pas_migree_hors_production(self, base, distante):
        """Un poste de développement dont le .env vise la base de production."""
        with pytest.raises(RuntimeError, match="MIGRER_BASE_DISTANTE"):
            migrate.run_migrations()
        assert _revision(base) == PRECEDENTE

    def test_une_base_distante_a_jour_ne_bloque_pas_le_demarrage(self, base, distante):
        _amener(base, TETE)
        migrate.run_migrations()
        assert _revision(base) == TETE

    def test_la_production_migre_sa_base(self, base, distante, monkeypatch):
        monkeypatch.setattr(settings, "ENV", "prod")
        migrate.run_migrations()
        assert _revision(base) == TETE

    def test_la_migration_voulue_se_demande_explicitement(self, base, distante, monkeypatch):
        monkeypatch.setattr(settings, "MIGRER_BASE_DISTANTE", True)
        migrate.run_migrations()
        assert _revision(base) == TETE

    def test_une_base_locale_se_migre(self, base):
        migrate.run_migrations()
        assert _revision(base) == TETE


def test_les_journaux_de_l_application_survivent_aux_migrations(base):
    """La configuration d'alembic.ini éteignait tous les journaux `hanabi.*` au démarrage."""
    acces = logging.getLogger("hanabi.acces")
    racine = logging.getLogger()
    avant = (list(racine.handlers), racine.level)

    migrate.run_migrations()

    assert not acces.disabled
    assert (list(racine.handlers), racine.level) == avant
