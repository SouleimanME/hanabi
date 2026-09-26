"""Fixtures partagees par la suite de tests."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from antibot_helper import solve_antibot

from app import antibot
from app.config import settings
from app.database import Base, base_locale, creer_moteur, get_db, normalise_url
from app.main import app
from app.models import Product, Promo, User
from app.ratelimit import limiter
from app.security import hash_password


# --- Anti-robots ---


@pytest.fixture(autouse=True)
def relax_antibot(monkeypatch):
    """Rend les barrieres anti-robots franchissables en test."""
    monkeypatch.setattr(settings, "POW_DIFFICULTY", 4)
    monkeypatch.setattr(settings, "MIN_FORM_SECONDS", 0.0)
    antibot._used.clear()
    antibot._failures.clear()
    yield
    antibot._used.clear()
    antibot._failures.clear()


@pytest.fixture
def antibot_for():
    """Fixture d'acces au solveur, pour les tests qui postent un formulaire."""
    return solve_antibot


# --- Recherche ---


@pytest.fixture(autouse=True)
def recherche_par_le_texte(monkeypatch):
    """Sans modèle par défaut : un modèle chargé en arrière-plan au milieu d'un
    test changerait ses résultats. Les tests du sens l'activent eux-mêmes."""
    monkeypatch.setattr(settings, "RECHERCHE_SEMANTIQUE", False)


# --- Courriels ---


@pytest.fixture(autouse=True)
def boite_courriels(monkeypatch):
    """Detourne les courriels vers une boite en memoire."""
    from app import mailer

    boite = mailer.ExpediteurMemoire()
    monkeypatch.setattr(mailer, "expediteur", boite)
    return boite


# --- Base de donnees ---

# Posee, la suite tourne sur ce PostgreSQL, comme la production, au lieu de SQLite
URL_POSTGRESQL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(scope="session")
def moteur_postgresql():
    """Schema cree une fois par session ; None sans TEST_DATABASE_URL."""
    if not URL_POSTGRESQL:
        yield None
        return
    url = normalise_url(URL_POSTGRESQL)
    # La suite vide toutes les tables entre deux tests
    if not base_locale(url):
        pytest.exit("TEST_DATABASE_URL doit viser une base locale : la suite en vide les tables.")
    moteur = creer_moteur(url)
    Base.metadata.drop_all(moteur)
    Base.metadata.create_all(moteur)
    yield moteur
    Base.metadata.drop_all(moteur)
    moteur.dispose()


@pytest.fixture
def moteur(moteur_postgresql):
    """Base vide pour chaque test."""
    if moteur_postgresql is None:
        # StaticPool : SQLite en memoire est propre a chaque connexion. Sans lui,
        # le client HTTP et le test verraient deux bases differentes.
        moteur = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(moteur)
        yield moteur
        moteur.dispose()
        return

    tables = ", ".join(
        moteur_postgresql.dialect.identifier_preparer.quote(t.name)
        for t in Base.metadata.sorted_tables
    )
    with moteur_postgresql.begin() as cx:
        # Une session oubliee par le test precedent echoue ici au lieu de tout bloquer
        cx.execute(text("set local lock_timeout = '5s'"))
        cx.execute(text(f"truncate {tables} restart identity cascade"))
    yield moteur_postgresql


@pytest.fixture
def db_session(moteur):
    TestingSession = sessionmaker(bind=moteur, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """Client HTTP branche sur la base de test."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Le limiteur de debit fausserait les tests : la route d'inscription est
    # plafonnee a 5 appels par minute, or plusieurs tests s'inscrivent.
    limiter.enabled = False

    # Pas de gestionnaire de contexte
    yield TestClient(app)

    app.dependency_overrides.clear()
    limiter.enabled = True


# --- Donnees de test ---


@pytest.fixture
def product(db_session):
    """Un produit a 20,00 EUR, 5 en stock."""
    p = Product(
        code="TST-001",
        name="Bol de test",
        category="Décoration",
        blurb="Un bol pour les tests.",
        price_cents=2000,
        stock=5,
        active=True,
        art="enso,#224A3F,#E4D7BF",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def expensive_product(db_session):
    """Un produit a 90,00 EUR : au-dessus du seuil de port offert (80 EUR)."""
    p = Product(
        code="TST-002",
        name="Katana de test",
        category="Figurines",
        blurb="Cher, pour tester la franchise de port.",
        price_cents=9000,
        stock=3,
        active=True,
        art="moon,#16140F,#E0382A",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def promos(db_session):
    """Jeu de codes promo couvrant les trois types."""
    items = {
        "percent": Promo(code="MOINS10", kind="percent", percent=10, active=True),
        "fixed": Promo(code="MOINS5EUR", kind="fixed", amount_cents=500, active=True),
        "free_shipping": Promo(code="PORTOFFERT", kind="free_shipping", active=True),
        "threshold": Promo(
            code="GROSPANIER", kind="percent", percent=20, min_subtotal_cents=10000, active=True
        ),
        "inactive": Promo(code="PERIME", kind="percent", percent=50, active=False),
    }
    db_session.add_all(items.values())
    db_session.commit()
    return items


@pytest.fixture
def user_factory(db_session):
    """Cree un utilisateur en base et renvoie (utilisateur, mot de passe)."""
    created = []

    def make(email="client@test.fr", password="MotDePasse1!", is_admin=False, name="Client Test"):
        u = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            is_admin=is_admin,
        )
        db_session.add(u)
        db_session.commit()
        db_session.refresh(u)
        created.append(u)
        return u, password

    return make


@pytest.fixture
def auth_header(client, user_factory):
    """En-tete Authorization pour un client connecte."""

    # `password` est transmis a `user_factory`
    def make(email="client@test.fr", is_admin=False, password="MotDePasse1!"):
        user, password = user_factory(email=email, is_admin=is_admin, password=password)
        res = client.post(
            "/auth/login",
            json={"email": email, "password": password, "antibot": solve_antibot("login")},
        )
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}, user

    return make
