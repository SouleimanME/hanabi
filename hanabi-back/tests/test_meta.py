"""Routes de service : racine et sonde de sante."""


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
        assert res.json() == {"status": "ok"}
