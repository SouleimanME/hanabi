"""Provisionnement du compte administrateur, et cloisonnement du compte demo."""
from datetime import datetime, timezone

import pytest

from app.config import settings
from app.models import User
from app.security import verify_password
from app.seed import ensure_admin, seed

BON_MOT_DE_PASSE = "Tr3s-Solide!2026"


@pytest.fixture
def sans_admin_configure(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAIL", "")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "")


@pytest.fixture
def admin_configure(monkeypatch):
    def apply(email="patron@hanabi.fr", password=BON_MOT_DE_PASSE):
        monkeypatch.setattr(settings, "ADMIN_EMAIL", email)
        monkeypatch.setattr(settings, "ADMIN_PASSWORD", password)

    return apply


class TestCompteDemo:
    def test_le_compte_demo_n_est_pas_administrateur(self, db_session, sans_admin_configure):
        """Ses identifiants sont publics : il ne doit avoir aucun privilege."""
        seed(db_session)

        demo = db_session.query(User).filter_by(email="demo@hanabi.fr").one()
        assert demo.is_admin is False

    def test_aucun_administrateur_par_defaut(self, db_session, sans_admin_configure):
        """Une mise en ligne sans configuration ne doit exposer aucun back-office."""
        seed(db_session)
        ensure_admin(db_session)

        assert db_session.query(User).filter_by(is_admin=True).count() == 0


class TestRetrogradationDesBasesAnciennes:
    """`seed` s'interrompt si le catalogue existe."""

    def test_le_compte_demo_administrateur_est_retrograde(
        self, db_session, sans_admin_configure, user_factory
    ):
        # Reproduit l'etat d'une base creee avant la separation des comptes.
        demo, _ = user_factory(email="demo@hanabi.fr", is_admin=True)

        ensure_admin(db_session)

        db_session.refresh(demo)
        assert demo.is_admin is False

    def test_retrogradation_meme_avec_un_autre_admin_configure(
        self, db_session, admin_configure, user_factory
    ):
        demo, _ = user_factory(email="demo@hanabi.fr", is_admin=True)
        admin_configure(email="patron@hanabi.fr")

        ensure_admin(db_session)

        db_session.refresh(demo)
        assert demo.is_admin is False
        assert db_session.query(User).filter_by(email="patron@hanabi.fr").one().is_admin is True

    def test_choix_delibere_respecte(self, db_session, admin_configure, user_factory):
        """Designer explicitement le compte demo comme admin doit etre respecte."""
        demo, _ = user_factory(email="demo@hanabi.fr", is_admin=True)
        admin_configure(email="demo@hanabi.fr")

        ensure_admin(db_session)

        db_session.refresh(demo)
        assert demo.is_admin is True

    def test_un_client_ordinaire_n_est_pas_touche(
        self, db_session, sans_admin_configure, user_factory
    ):
        autre, _ = user_factory(email="client@test.fr", is_admin=False)

        ensure_admin(db_session)

        db_session.refresh(autre)
        assert autre.is_admin is False


class TestProvisionnement:
    def test_cree_l_administrateur_depuis_l_environnement(self, db_session, admin_configure):
        admin_configure()

        ensure_admin(db_session)

        admin = db_session.query(User).filter_by(email="patron@hanabi.fr").one()
        assert admin.is_admin is True
        # Le mot de passe n'est jamais stocke en clair.
        assert admin.password_hash.startswith("$2b$")

    def test_idempotent(self, db_session, admin_configure):
        """Appele a chaque demarrage : ne doit pas creer de doublon."""
        admin_configure()

        ensure_admin(db_session)
        ensure_admin(db_session)

        assert db_session.query(User).filter_by(email="patron@hanabi.fr").count() == 1

    def test_promeut_un_compte_existant(self, db_session, admin_configure, user_factory):
        """Permet de designer un administrateur apres la mise en service."""
        user_factory(email="patron@hanabi.fr", is_admin=False)
        admin_configure()

        ensure_admin(db_session)

        assert db_session.query(User).filter_by(email="patron@hanabi.fr").one().is_admin is True

    def test_email_insensible_a_la_casse(self, db_session, admin_configure):
        admin_configure(email="Patron@Hanabi.FR")

        ensure_admin(db_session)

        assert db_session.query(User).filter_by(email="patron@hanabi.fr").count() == 1

    @pytest.mark.parametrize("faible", ["demo1234", "password123", "court", "aaaaaaaaaaaa"])
    def test_refuse_un_mot_de_passe_faible(self, db_session, admin_configure, faible):
        """Un administrateur au mot de passe trivial annule l'interet de la mesure."""
        admin_configure(password=faible)

        ensure_admin(db_session)

        assert db_session.query(User).filter_by(is_admin=True).count() == 0

    def test_refuse_si_une_seule_variable_est_fournie(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "ADMIN_EMAIL", "patron@hanabi.fr")
        monkeypatch.setattr(settings, "ADMIN_PASSWORD", "")

        ensure_admin(db_session)

        assert db_session.query(User).filter_by(is_admin=True).count() == 0


class TestMotDePasseQuiFaitFoi:
    """ADMIN_PASSWORD, changé sur l'hébergeur, réinitialise le compte au démarrage."""

    def test_un_nouveau_mot_de_passe_remplace_l_ancien(self, db_session, admin_configure):
        admin_configure()
        ensure_admin(db_session)
        admin_configure(password="Autre-Secret!2027")

        ensure_admin(db_session)

        admin = db_session.query(User).filter_by(email="patron@hanabi.fr").one()
        assert verify_password("Autre-Secret!2027", admin.password_hash)
        assert not verify_password(BON_MOT_DE_PASSE, admin.password_hash)
        # Les sessions ouvertes avec l'ancien mot de passe tombent
        assert admin.token_version == 1

    def test_le_meme_mot_de_passe_ne_ferme_aucune_session(self, db_session, admin_configure):
        admin_configure()
        ensure_admin(db_session)
        ensure_admin(db_session)

        assert db_session.query(User).filter_by(email="patron@hanabi.fr").one().token_version == 0

    def test_le_back_office_de_demonstration_n_est_pas_un_administrateur(
        self, db_session, admin_configure
    ):
        admin_configure(email="hanabi@atelier.fr")

        ensure_admin(db_session)

        assert db_session.query(User).filter_by(email="hanabi@atelier.fr").count() == 0

    def test_un_compte_efface_n_est_pas_ranime(self, db_session, admin_configure, user_factory):
        compte, _ = user_factory(email="patron@hanabi.fr", is_admin=False)
        compte.anonymise_le = datetime.now(timezone.utc)
        db_session.commit()
        admin_configure()

        ensure_admin(db_session)

        db_session.refresh(compte)
        assert compte.is_admin is False
