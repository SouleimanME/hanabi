"""Routes de service : racine et sonde de sante."""
import pytest

from app.database import get_db
from app.main import app


@pytest.fixture
def base_en_panne():
    """Remplace la session de la sonde par une base qui refuse tout."""

    def poser(message: str):
        class Muette:
            def execute(self, *_):
                raise RuntimeError(message)

        app.dependency_overrides[get_db] = lambda: iter([Muette()])

    yield poser
    app.dependency_overrides.pop(get_db, None)


class TestRacine:
    def test_la_racine_ne_renvoie_plus_un_404(self, client):
        """Ouvrir l'adresse de l'API dans un navigateur donnait « Not Found »."""
        res = client.get("/")

        assert res.status_code == 200

    def test_la_racine_oriente_vers_les_routes_utiles(self, client):
        body = client.get("/").json()

        assert body["status"] == "ok"
        assert body["documentation"] == "/docs"
        assert body["sante"] == "/health"


class TestSante:
    def test_sonde_de_sante(self, client):
        """Route appelee par l'hebergeur pour savoir si le service repond."""
        res = client.get("/health")

        assert res.status_code == 200
        assert res.json() == {
            "status": "ok",
            "base": "ok",
            "courriels": {"en_attente": 0, "abandonnes": 0},
        }

    def test_la_sonde_signale_les_courriels_abandonnes(self, client, db_session):
        """Une file en echec ne se voit nulle part ailleurs."""
        from app import models

        db_session.add(
            models.OutboxEmail(
                destinataire="a@b.fr", sujet="s", texte="t", statut="abandonne", tentatives=5
            )
        )
        db_session.commit()

        res = client.get("/health")
        body = res.json()

        assert body["status"] == "degrade"
        assert body["courriels"]["abandonnes"] == 1
        # Pas de 503 : le service repond, prend des commandes et sert des pages
        assert res.status_code == 200

    def test_les_messages_en_attente_ne_degradent_pas_la_sonde(self, client, db_session):
        """C'est l'etat normal d'un message entre son ecriture et sa remise."""
        from app import models

        db_session.add(models.OutboxEmail(destinataire="a@b.fr", sujet="s", texte="t"))
        db_session.commit()

        body = client.get("/health").json()

        assert body["status"] == "ok"
        assert body["courriels"]["en_attente"] == 1

    def test_la_sonde_interroge_reellement_la_base(self, client, base_en_panne):
        """Une base injoignable doit faire rougir la sonde."""
        base_en_panne("connexion refusee")
        res = client.get("/health")

        # 503 et non 500 : c'est le code que les repartiteurs de charge et les
        # hebergeurs savent lire pour retirer une instance du service.
        assert res.status_code == 503
        body = res.json()
        assert body["status"] == "degrade"
        assert body["base"] == "injoignable"

    def test_la_sonde_ne_divulgue_pas_le_detail_de_la_panne(self, client, base_en_panne):
        """Le message du pilote reste dans le journal, pas dans la reponse."""
        base_en_panne("could not connect to host db-prod.interne:5432")
        corps = client.get("/health").text

        assert "db-prod.interne" not in corps
        assert "5432" not in corps
