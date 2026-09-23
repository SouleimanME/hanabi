"""Achats simultanes sur le dernier article."""
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.ratelimit import limiter

from test_orders import checkout_payload


def _en_parallele(taches):
    """Lance les taches ensemble et rend leurs resultats."""
    depart = threading.Barrier(len(taches))
    resultats = [None] * len(taches)

    def executer(indice, tache):
        depart.wait()
        try:
            resultats[indice] = tache()
        except Exception as erreur:  # noqa: BLE001 - remonte tel quel a l'assertion
            resultats[indice] = erreur

    fils = [
        threading.Thread(target=executer, args=(i, t)) for i, t in enumerate(taches)
    ]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join(timeout=30)
    return resultats


@pytest.fixture
def fabrique(tmp_path):
    """Base de test sur fichier, une connexion par fil."""
    moteur = create_engine(
        f"sqlite:///{tmp_path / 'concurrence.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )
    Base.metadata.create_all(moteur)
    return sessionmaker(bind=moteur, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db_session(fabrique):
    """Session d'inspection, distincte de celles des requetes."""
    session = fabrique()
    yield session
    session.close()


@pytest.fixture
def client(fabrique):
    """Client HTTP dont chaque requete ouvre sa propre session."""

    def par_requete():
        session = fabrique()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = par_requete
    limiter.enabled = False
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.enabled = True


def _ajouter(fabrique, **champs):
    session = fabrique()
    produit = models.Product(
        category="Collection", blurb="Article de test", active=True,
        art="enso,#224A3F,#E4D7BF", **champs,
    )
    session.add(produit)
    session.commit()
    session.refresh(produit)
    session.close()
    return produit


@pytest.fixture
def dernier_article(fabrique):
    """Un produit dont il ne reste qu'une unite."""
    return _ajouter(fabrique, code="RARE-001", name="Piece unique", price_cents=4900, stock=1)


@pytest.fixture
def product(fabrique):
    """Cinq unites, comme la fixture commune de la suite."""
    return _ajouter(fabrique, code="TST-001", name="Bol de test", price_cents=2000, stock=5)


class TestDernierArticle:
    def test_un_seul_acheteur_l_emporte(self, client, db_session, dernier_article):
        """Huit acheteurs, un article, une seule commande."""
        charge = checkout_payload(dernier_article.id, qty=1)
        reponses = _en_parallele(
            [lambda: client.post("/orders/checkout", json=charge) for _ in range(8)]
        )

        codes = [r.status_code for r in reponses]
        assert codes.count(201) == 1, f"attendu une seule reussite, obtenu {codes}"
        # Les autres sont refuses proprement : 409 pour stock insuffisant
        assert all(c in (201, 409) for c in codes), f"code inattendu dans {codes}"

        db_session.expire_all()
        assert db_session.get(models.Product, dernier_article.id).stock == 0
        assert db_session.query(models.Order).count() == 1

    def test_le_stock_ne_passe_jamais_sous_zero(self, client, db_session, dernier_article):
        charge = checkout_payload(dernier_article.id, qty=1)
        _en_parallele([lambda: client.post("/orders/checkout", json=charge) for _ in range(12)])

        db_session.expire_all()
        assert db_session.get(models.Product, dernier_article.id).stock >= 0

    def test_autant_de_commandes_que_d_unites(self, client, db_session, product):
        """Cinq en stock, dix acheteurs : exactement cinq commandes."""
        charge = checkout_payload(product.id, qty=1)
        reponses = _en_parallele(
            [lambda: client.post("/orders/checkout", json=charge) for _ in range(10)]
        )

        codes = [r.status_code for r in reponses]
        assert codes.count(201) == 5, f"attendu cinq reussites, obtenu {codes}"

        db_session.expire_all()
        assert db_session.get(models.Product, product.id).stock == 0
        assert db_session.query(models.Order).count() == 5


class TestFiletDeSecurite:
    def test_la_base_refuse_un_stock_negatif(self, db_session, dernier_article):
        """Le garde-fou de dernier recours, independant du code applicatif."""
        # Relu dans la session d'inspection : la fixture rend un objet detache,
        # dont les modifications ne partiraient nulle part.
        produit = db_session.get(models.Product, dernier_article.id)
        produit.stock = -1

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestIdempotenceSousConcurrence:
    def test_le_double_clic_ne_cree_qu_une_commande(self, client, db_session, product):
        """Le cas reel : deux requetes identiques a quelques millisecondes."""
        from app.idempotency import EN_TETE

        charge = checkout_payload(product.id, qty=1)
        cle = {EN_TETE: "double-clic-000000000001"}
        reponses = _en_parallele(
            [lambda: client.post("/orders/checkout", json=charge, headers=cle) for _ in range(6)]
        )

        codes = [r.status_code for r in reponses]
        # 201 pour la creation et pour les rejeux, 409 pour ceux qui arrivent
        # pendant que la premiere est encore en cours.
        assert all(c in (201, 409) for c in codes), f"code inattendu dans {codes}"
        assert db_session.query(models.Order).count() == 1
        assert db_session.query(models.OutboxEmail).count() == 1
