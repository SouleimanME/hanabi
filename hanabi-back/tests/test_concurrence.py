"""Achats simultanes sur le dernier article.

CE QUI MANQUAIT. La suite contenait deja un test intitule « deux commandes
concurrentes », mais il envoyait ses deux requetes l'une APRES l'autre. Il
prouvait donc que l'`UPDATE` conditionnel refuse un stock insuffisant - ce qui
compte - sans jamais mettre deux requetes en vol en meme temps. Or c'est
exactement la que le bogue se cache : entre un `SELECT stock` et l'`UPDATE` qui
suit, une seconde requete peut passer, et deux acheteurs repartent avec le meme
dernier article.

Ces tests lancent donc de vrais fils d'execution. La garantie tient a trois
choses, et chacune est verifiee ici :

  - le decrement est un `UPDATE ... WHERE stock >= qty`, jamais une lecture
    suivie d'une ecriture ;
  - le `rowcount` decide, et non une relecture du stock ;
  - une contrainte `CHECK (stock >= 0)` reste en filet dernier, pour le jour ou
    un futur chemin de code oublierait les deux premieres.

LIMITE ASSUMEE. SQLite serialise les ecritures : le parallelisme reel y est
moindre que sur PostgreSQL. La conclusion, elle, ne change pas - si le code
lisait puis ecrivait, l'entrelacement se produirait meme ici, et exactement
une commande doit passer dans tous les cas.
"""
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
    """Lance les taches ensemble et rend leurs resultats.

    Une barriere synchronise le depart : sans elle, le premier fil aurait fini
    avant que le dernier ne commence, et l'on retomberait sur un test sequentiel
    portant un nom trompeur - le defaut meme que ce fichier corrige.
    """
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
    """Base de test sur FICHIER, une connexion par fil.

    Le `db_session` commun a la suite ne convient pas ici, et c'est instructif :
    il sert UNE seule `Session` a toutes les requetes, via `StaticPool` sur une
    base en memoire. Une `Session` SQLAlchemy n'est pas sure en concurrence -
    plusieurs fils qui la partagent se volent leur transaction, et l'on obtient
    « This transaction is closed » plutot que le comportement qu'on voulait
    mesurer. Ce serait un artefact du test, pas un defaut du code.

    En production, `get_db` ouvre une session par requete. On reproduit donc
    cela : une base sur fichier, un pool ordinaire, une session neuve a chaque
    appel. `timeout` laisse SQLite attendre la levee du verrou d'ecriture au
    lieu d'echouer aussitot sur « database is locked ».
    """
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
    """Un produit dont il ne reste qu'UNE unite."""
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
        # Les autres sont refuses proprement : 409 pour stock insuffisant. Aucun
        # 500 - une collision prevue n'est pas une panne, et le client doit
        # pouvoir distinguer les deux.
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
        """Le garde-fou de dernier recours, independant du code applicatif.

        Il ne sert a rien tant que l'`UPDATE` conditionnel fait son travail.
        Il sert le jour ou quelqu'un ecrit un autre chemin de decrement - une
        commande d'administration, un import, une reprise de donnees - et oublie
        la condition. La base, elle, ne l'oublie pas.
        """
        # Relu dans la session d'inspection : la fixture rend un objet detache,
        # dont les modifications ne partiraient nulle part.
        produit = db_session.get(models.Product, dernier_article.id)
        produit.stock = -1

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestIdempotenceSousConcurrence:
    def test_le_double_clic_ne_cree_qu_une_commande(self, client, db_session, product):
        """Le cas reel : deux requetes identiques a quelques millisecondes.

        C'est ici que la contrainte unique gagne sa place. Une verification
        prealable - lire la cle, puis inserer si absente - laisserait passer les
        deux, puisqu'aucune des deux ne voit encore l'autre.
        """
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
