"""Failles trouvees a l'audit, et le verrou qui les referme."""
import pytest

from antibot_helper import solve_antibot

from app import rgpd
from app.passwords import MAX_BYTES, validate_password
from app.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, ensure_public_admin


@pytest.fixture
def demo_admin(db_session, client):
    """En-tete du compte vitrine, dont les identifiants sont publics."""
    ensure_public_admin(db_session)
    res = client.post(
        "/auth/login",
        json={
            "email": DEMO_ADMIN_EMAIL,
            "password": DEMO_ADMIN_PASSWORD,
            "antibot": solve_antibot("login"),
        },
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def vrai_admin(auth_header):
    entete, _ = auth_header(email="patron@hanabi.fr", is_admin=True)
    return entete


class TestFichierClientPublic:
    """Le compte vitrine lisait la base clients en entier."""

    def test_le_compte_vitrine_ne_lit_aucune_adresse(self, client, demo_admin, user_factory):
        user_factory(email="marie.durand@exemple.fr", name="Marie Durand")

        res = client.get("/admin/users", headers=demo_admin)
        assert res.status_code == 200
        corps = res.json()

        assert corps["masque"] is True
        adresses = [item["email"] for item in corps["items"]]
        assert "marie.durand@exemple.fr" not in adresses
        # La forme survit, le domaine reste lisible, les lignes restent
        # distinguables, mais rien n'est joignable.
        assert any(a.startswith("m") and a.endswith("@exemple.fr") for a in adresses)

    def test_le_compte_vitrine_ne_lit_ni_ville_ni_naissance(
        self, client, demo_admin, db_session, user_factory
    ):
        user, _ = user_factory(email="paul@exemple.fr", name="Paul Martin")
        user.city = "Bordeaux"
        user.birthdate = "1990-04-12"
        db_session.commit()

        items = client.get("/admin/users", headers=demo_admin).json()["items"]
        vise = next(i for i in items if i["name"].startswith("Paul"))

        assert vise["city"] != "Bordeaux"
        assert vise["birthdate"] is None
        # Le nom de famille tombe, le prenom reste : l'ecran doit rester lisible.
        assert vise["name"] == "Paul M."

    def test_le_vrai_administrateur_lit_tout(self, client, vrai_admin, user_factory):
        """La correction ne doit gener personne d'autre."""
        user_factory(email="marie.durand@exemple.fr", name="Marie Durand")

        corps = client.get("/admin/users", headers=vrai_admin).json()

        assert corps["masque"] is False
        assert "marie.durand@exemple.fr" in [i["email"] for i in corps["items"]]

    def test_l_export_csv_est_masque_pour_le_compte_vitrine(self, client, demo_admin):
        res = client.get("/admin/orders.csv", headers=demo_admin)
        assert res.status_code == 200
        assert "@" not in res.text or "***" in res.text


class TestRevocationDesSessions:
    """Un JWT survivait au geste cense le tuer."""

    def test_changer_son_mot_de_passe_ferme_les_sessions(self, client, auth_header):
        entete, _ = auth_header(email="cible@test.fr", password="MotDePasse1!")

        # Le jeton fonctionne avant.
        assert client.get("/auth/me", headers=entete).status_code == 200

        res = client.post(
            "/compte/mot-de-passe",
            headers=entete,
            json={"ancien": "MotDePasse1!", "nouveau": "NouveauSecret9?"},
        )
        assert res.status_code == 204, res.text

        # Et plus apres. C'est tout l'objet du correctif.
        assert client.get("/auth/me", headers=entete).status_code == 401

    def test_effacer_son_compte_ferme_les_sessions(self, client, auth_header):
        """Le condensat rendu inutilisable empeche de se reconnecter."""
        entete, _ = auth_header(email="partant@test.fr", password="MotDePasse1!")

        res = client.post(
            "/compte/suppression",
            headers=entete,
            json={
                "password": "MotDePasse1!",
                "confirmation": rgpd.FORMULE_CONFIRMATION,
            },
        )
        assert res.status_code == 200, res.text

        assert client.get("/auth/me", headers=entete).status_code == 401

    def test_les_autres_comptes_ne_sont_pas_touches(self, client, auth_header):
        """La revocation vise un compte, pas tout le monde."""
        cible, _ = auth_header(email="cible2@test.fr", password="MotDePasse1!")
        temoin, _ = auth_header(email="temoin@test.fr", password="AutreSecret7!")

        client.post(
            "/compte/mot-de-passe",
            headers=cible,
            json={"ancien": "MotDePasse1!", "nouveau": "NouveauSecret9?"},
        )

        assert client.get("/auth/me", headers=temoin).status_code == 200


class TestTroncatureBcrypt:
    """bcrypt ne lit que 72 octets et jette le reste, en silence."""

    def test_refuse_au_dela_de_72_octets(self):
        assert validate_password("A" * (MAX_BYTES + 1)) is not None

    def test_accepte_exactement_72_octets(self):
        assert validate_password("Aa1!" + "bcdefghij" * 7 + "kzyx5") is None

    def test_compte_en_octets_et_non_en_caracteres(self):
        """« é » pese deux octets. Quarante accents depassent deja le plafond."""
        accentue = "é" * 40
        assert len(accentue) < MAX_BYTES
        assert len(accentue.encode("utf-8")) > MAX_BYTES
        assert validate_password(accentue) is not None


class TestCorsEnProduction:
    """`allow_credentials=True` avec une origine generique fait renvoyer a Starlette l'origine demandee."""

    def test_l_etoile_est_refusee_en_production(self, monkeypatch):
        from app.config import Settings, _verifie_cors

        cfg = Settings(ENV="prod", SECRET_KEY="x" * 40, CORS_ORIGINS="*")
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            _verifie_cors(cfg)

    def test_une_origine_exacte_passe(self):
        from app.config import Settings, _verifie_cors

        cfg = Settings(
            ENV="prod", SECRET_KEY="x" * 40, CORS_ORIGINS="https://hanabi-6x9.pages.dev"
        )
        assert _verifie_cors(cfg) is cfg


class TestPanierSurdimensionne:
    """`items` n'avait aucune borne de longueur."""

    def test_le_panier_est_borne(self, client, product):
        trop = {"items": [{"product_id": product.id, "qty": 1} for _ in range(500)]}
        assert client.post("/orders/quote", json=trop).status_code == 422

    def test_un_panier_normal_passe(self, client, product):
        normal = {"items": [{"product_id": product.id, "qty": 2}]}
        res = client.post("/orders/quote", json=normal)
        assert res.status_code == 200
        assert res.json()["subtotal_cents"] == product.price_cents * 2

    def test_une_seule_lecture_du_catalogue(self, client, db_session, product):
        """Le cout ne doit pas dependre de la forme du panier."""
        from sqlalchemy import event

        from app import models

        moteur = db_session.get_bind()
        lectures = []

        def compter(conn, cursor, requete, params, contexte, executemany):
            if "products" in requete.lower():
                lectures.append(requete)

        event.listen(moteur, "before_cursor_execute", compter)
        try:
            client.post(
                "/orders/quote",
                json={"items": [{"product_id": product.id, "qty": 1} for _ in range(40)]},
            )
        finally:
            event.remove(moteur, "before_cursor_execute", compter)

        assert len(lectures) == 1, f"{len(lectures)} lectures du catalogue au lieu d'une"


def _commande(db_session, produit, numero: str, adresse: str):
    """Une commande d'une ligne."""
    from app import models

    commande = models.Order(
        number=numero, email=adresse, status="paid",
        subtotal_cents=1000, discount_cents=0, shipping_cents=0, total_cents=1000,
    )
    db_session.add(commande)
    db_session.flush()
    db_session.add(models.OrderItem(
        order_id=commande.id, product_id=produit.id, name=produit.name,
        art=produit.art, category=produit.category, unit_price_cents=1000, qty=1,
    ))
    db_session.commit()
    return commande


class TestInjectionDeFormule:
    """Le CSV est ecrit pour un tableur, qui n'ouvre pas du texte mais un classeur."""

    def test_une_adresse_en_formule_est_neutralisee(
        self, client, vrai_admin, db_session, product
    ):
        _commande(db_session, product, "HNB-TEST-1", "=1+1@exemple.fr")

        texte = client.get("/admin/orders.csv", headers=vrai_admin).text

        assert '"=1+1@exemple.fr"' not in texte
        assert "'=1+1@exemple.fr" in texte

    def test_une_adresse_ordinaire_n_est_pas_touchee(
        self, client, vrai_admin, db_session, product
    ):
        _commande(db_session, product, "HNB-TEST-2", "marie@exemple.fr")

        texte = client.get("/admin/orders.csv", headers=vrai_admin).text

        assert "marie@exemple.fr" in texte
        assert "'marie@exemple.fr" not in texte
