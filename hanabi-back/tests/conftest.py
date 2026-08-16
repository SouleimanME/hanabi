"""Fixtures partagees par la suite de tests.

Chaque test recoit une base SQLite en memoire, vierge et isolee. On evite
ainsi toute dependance a `atelier.db` : la suite tourne sur un poste neuf
comme en integration continue, sans etat residuel entre deux executions.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from antibot_helper import solve_antibot

from app import antibot
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Product, Promo, User
from app.ratelimit import limiter
from app.security import hash_password


# --------------------------------------------------------------------------
# Anti-robots
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def relax_antibot(monkeypatch):
    """Rend les barrieres anti-robots franchissables en test.

    On ne les desactive pas : les tests continuent de traverser le vrai code de
    verification, ce qui detecte une regression de cablage. On abaisse seulement
    le cout - une preuve a 18 bits par appel et une attente de 1,5 s par
    formulaire rendraient la suite inutilisablement lente.
    """
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


# --------------------------------------------------------------------------
# Courriels
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def boite_courriels(monkeypatch):
    """Detourne les courriels vers une boite en memoire.

    Applique partout, y compris aux tests qui n'y touchent pas : sans cela, la
    sortie par defaut ecrirait de vrais fichiers .eml dans `var/courriels/` a
    chaque commande de test, et la suite laisserait des dechets derriere elle.

    La remise, elle, n'est jamais automatique en test : le `client` ci-dessous
    ne declenche pas le lifespan, donc l'ouvrier de fond ne demarre pas, et les
    tests qui veulent voir partir un message appellent `traiter_lot` eux-memes.
    Une tache de fond et des assertions font mauvais menage - le test passerait
    ou non selon la vitesse de la machine.
    """
    from app import mailer

    boite = mailer.ExpediteurMemoire()
    monkeypatch.setattr(mailer, "expediteur", boite)
    return boite


@pytest.fixture
def db_session():
    # StaticPool : SQLite en memoire est propre a chaque connexion. Sans lui,
    # le client HTTP et le test verraient deux bases differentes.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Client HTTP branche sur la base de test."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Le limiteur de debit fausserait les tests : la route d'inscription est
    # plafonnee a 5 appels par minute, or plusieurs tests s'inscrivent.
    limiter.enabled = False

    # Pas de gestionnaire de contexte : on ne veut pas declencher le lifespan,
    # qui creerait les tables et injecterait le jeu de donnees de demo dans la
    # base de production.
    yield TestClient(app)

    app.dependency_overrides.clear()
    limiter.enabled = True


# --------------------------------------------------------------------------
# Donnees de test
# --------------------------------------------------------------------------


@pytest.fixture
def product(db_session):
    """Un produit a 20,00 EUR, 5 en stock."""
    p = Product(
        code="TST-001",
        name="Bol de test",
        category="Tradition",
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
        category="Collection",
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

    # `password` est transmis a `user_factory` : les tests du compte ont besoin
    # de CONNAITRE le mot de passe courant, que plusieurs routes exigent avant
    # de laisser changer un identifiant.
    def make(email="client@test.fr", is_admin=False, password="MotDePasse1!"):
        user, password = user_factory(email=email, is_admin=is_admin, password=password)
        res = client.post(
            "/auth/login",
            json={"email": email, "password": password, "antibot": solve_antibot("login")},
        )
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}, user

    return make
