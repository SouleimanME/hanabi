"""Routes de service : racine et sonde de sante."""
import pytest

from app.database import get_db
from app.main import app


@pytest.fixture
def base_en_panne():
    """Remplace la session de la sonde par une base qui refuse tout.

    On passe par `dependency_overrides`, le point d'extension prevu par FastAPI,
    plutot que par un en-tete de test : le code de production n'a pas a savoir
    qu'il est teste, et une branche « si en-tete de test » finit toujours par
    exister aussi en production.
    """

    def poser(message: str):
        class Muette:
            def execute(self, *_):
                raise RuntimeError(message)

        app.dependency_overrides[get_db] = lambda: iter([Muette()])

    yield poser
    app.dependency_overrides.pop(get_db, None)


class TestRacine:
    def test_la_racine_ne_renvoie_plus_un_404(self, client):
        """Ouvrir l'adresse de l'API dans un navigateur donnait « Not Found »,
        ce qui laisse croire a une panne alors que le service tourne."""
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
        """Une file en echec ne se voit nulle part ailleurs.

        L'ouvrier echoue en silence PAR CONSTRUCTION : son role est d'absorber
        les pannes de relais sans les faire remonter au visiteur. Sans cette
        ligne dans la sonde, on decouvrirait le probleme par un client qui n'a
        jamais recu sa confirmation.
        """
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
        # Pas de 503 : le service repond, prend des commandes et sert des pages.
        # Seule la remise du courrier est en defaut, et retirer l'instance du
        # service aggraverait une panne partielle.
        assert res.status_code == 200

    def test_les_messages_en_attente_ne_degradent_pas_la_sonde(self, client, db_session):
        """C'est l'etat NORMAL d'un message entre son ecriture et sa remise."""
        from app import models

        db_session.add(models.OutboxEmail(destinataire="a@b.fr", sujet="s", texte="t"))
        db_session.commit()

        body = client.get("/health").json()

        assert body["status"] == "ok"
        assert body["courriels"]["en_attente"] == 1

    def test_la_sonde_interroge_reellement_la_base(self, client, base_en_panne):
        """Une base injoignable doit faire rougir la sonde.

        C'est tout l'interet du changement. L'ancienne version rendait
        `{"status": "ok"}` en dur : elle ne prouvait que la presence du
        processus Python, alors que la panne la plus frequente est en aval. Une
        base en veille, un pool epuise ou un mot de passe expire laissaient la
        sonde au vert pendant que chaque page renvoyait une erreur, si bien que
        la surveillance ne redemarrait rien et que personne n'etait prevenu.
        """
        base_en_panne("connexion refusee")
        res = client.get("/health")

        # 503 et non 500 : c'est le code que les repartiteurs de charge et les
        # hebergeurs savent lire pour retirer une instance du service.
        assert res.status_code == 503
        body = res.json()
        assert body["status"] == "degrade"
        assert body["base"] == "injoignable"

    def test_la_sonde_ne_divulgue_pas_le_detail_de_la_panne(self, client, base_en_panne):
        """Le message du pilote reste dans le journal, pas dans la reponse.

        Une sonde de sante est souvent publique, et les erreurs de connexion
        des pilotes de base citent volontiers le nom d'hote, le port et le nom
        de la base.
        """
        base_en_panne("could not connect to host db-prod.interne:5432")
        corps = client.get("/health").text

        assert "db-prod.interne" not in corps
        assert "5432" not in corps
