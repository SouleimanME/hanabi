"""Compte vitrine du back-office.

Ses identifiants sont publies dans la fenetre de connexion : n'importe qui peut
s'y connecter. Ces tests verrouillent les deux proprietes qui rendent ce choix
tenable - le compte ouvre bien le back-office, et il ne peut rien y modifier.
"""
import pytest

from antibot_helper import solve_antibot

from app.config import settings
from app.models import User
from app.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, ensure_public_admin


@pytest.fixture
def demo_admin(db_session, client):
    """Provisionne le compte vitrine et renvoie son en-tete d'authentification."""
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


class TestProvisionnement:
    def test_cree_un_administrateur(self, db_session):
        ensure_public_admin(db_session)

        compte = db_session.query(User).filter_by(email=DEMO_ADMIN_EMAIL).one()
        assert compte.is_admin is True

    def test_idempotent(self, db_session):
        """Appelee a chaque demarrage : ne doit pas creer de doublon."""
        ensure_public_admin(db_session)
        ensure_public_admin(db_session)

        assert db_session.query(User).filter_by(email=DEMO_ADMIN_EMAIL).count() == 1

    def test_remet_le_mot_de_passe_a_niveau(self, db_session):
        """Changer la constante doit suffire, meme sur une base existante.

        Sans cela, les identifiants affiches dans l'interface finiraient par ne
        plus ouvrir quoi que ce soit.
        """
        ensure_public_admin(db_session)
        compte = db_session.query(User).filter_by(email=DEMO_ADMIN_EMAIL).one()
        compte.password_hash = "condensat-obsolete"
        db_session.commit()

        ensure_public_admin(db_session)

        db_session.refresh(compte)
        assert compte.password_hash != "condensat-obsolete"

    def test_desactivable(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PUBLIC_ADMIN_DEMO", False)

        ensure_public_admin(db_session)

        assert db_session.query(User).filter_by(email=DEMO_ADMIN_EMAIL).count() == 0


class TestLectureSeule:
    def test_peut_consulter_le_tableau_de_bord(self, client, demo_admin):
        assert client.get("/admin/stats", headers=demo_admin).status_code == 200
        assert client.get("/admin/analytics", headers=demo_admin).status_code == 200
        assert client.get("/admin/products", headers=demo_admin).status_code == 200

    def test_se_declare_en_lecture_seule(self, client, demo_admin):
        res = client.get("/admin/whoami", headers=demo_admin)

        assert res.status_code == 200
        assert res.json()["readonly"] is True

    @pytest.mark.parametrize(
        "methode,route,corps",
        [
            ("post", "/admin/products", {
                "code": "PIRATE", "name": "Injecte", "category": "Tradition",
                "blurb": "Ne doit pas exister", "price_cents": 100, "stock": 1,
            }),
            ("patch", "/admin/products/1", {"price_cents": 1}),
            ("delete", "/admin/products/1", None),
            ("post", "/admin/promos", {"code": "GRATUIT", "kind": "percent", "percent": 100}),
            ("delete", "/admin/promos/1", None),
            ("patch", "/admin/users/1/admin?is_admin=true", None),
        ],
    )
    def test_toute_ecriture_est_refusee(self, client, demo_admin, product, methode, route, corps):
        appel = getattr(client, methode)
        res = appel(route, headers=demo_admin, **({"json": corps} if corps else {}))

        assert res.status_code == 403, res.text
        assert "demonstration" in res.json()["detail"].lower()

    def test_un_vrai_administrateur_garde_ses_droits(self, client, auth_header):
        """Le garde-fou ne doit viser que le compte vitrine."""
        headers, _ = auth_header(email="patron@hanabi.fr", is_admin=True)

        res = client.post("/admin/promos", headers=headers, json={
            "code": "REEL10", "kind": "percent", "percent": 10,
        })

        assert res.status_code == 201, res.text

    def test_le_bridage_est_desactivable(self, client, db_session, demo_admin, monkeypatch):
        """`DEMO_ADMIN_READONLY=0` rend les droits complets, en connaissance de cause."""
        monkeypatch.setattr(settings, "DEMO_ADMIN_READONLY", False)

        res = client.post("/admin/promos", headers=demo_admin, json={
            "code": "OUVERT", "kind": "percent", "percent": 5,
        })

        assert res.status_code == 201, res.text
