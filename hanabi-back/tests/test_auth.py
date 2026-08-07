"""Inscription, connexion, protection des routes et barrieres anti-robots."""
import time

import pytest

from app import antibot
from app.config import settings

from antibot_helper import solve_antibot, wrong_nonce

BON_MOT_DE_PASSE = "MotDePasse1!"


def register_payload(**overrides):
    payload = {
        "name": "Ada Lovelace",
        "email": "ada@test.fr",
        "password": BON_MOT_DE_PASSE,
        "antibot": solve_antibot("register"),
    }
    payload.update(overrides)
    return payload


def login_payload(email, password, **overrides):
    payload = {"email": email, "password": password, "antibot": solve_antibot("login")}
    payload.update(overrides)
    return payload


class TestInscription:
    def test_inscription_renvoie_un_jeton(self, client):
        res = client.post("/auth/register", json=register_payload())

        assert res.status_code == 201, res.text
        body = res.json()
        assert body["access_token"]
        assert body["user"]["email"] == "ada@test.fr"

    def test_le_mot_de_passe_n_est_jamais_renvoye(self, client):
        res = client.post("/auth/register", json=register_payload())

        assert "password" not in res.text
        assert BON_MOT_DE_PASSE not in res.text

    def test_le_mot_de_passe_est_hache_en_base(self, client, db_session):
        from app.models import User

        client.post("/auth/register", json=register_payload())

        user = db_session.query(User).filter_by(email="ada@test.fr").one()
        assert user.password_hash != BON_MOT_DE_PASSE
        assert user.password_hash.startswith("$2b$")  # empreinte bcrypt

    def test_email_deja_pris(self, client):
        client.post("/auth/register", json=register_payload())

        # Nouveau bloc antibot : un defi ne sert qu'une fois.
        res = client.post("/auth/register", json=register_payload())
        assert res.status_code == 409

    def test_email_invalide_rejete(self, client):
        res = client.post("/auth/register", json=register_payload(email="pas-un-email"))
        assert res.status_code == 422

    def test_mot_de_passe_trop_court_rejete(self, client):
        res = client.post("/auth/register", json=register_payload(password="court"))
        assert res.status_code == 422

    def test_les_champs_optionnels_sont_enregistres(self, client, db_session):
        """Regression : ces champs etaient collectes par le front puis perdus."""
        from app.models import User

        client.post(
            "/auth/register",
            json=register_payload(
                civility="F",
                birthdate="1815-12-10",
                phone="+33 6 12 34 56 78",
                addr="12 rue des Tests",
                cp="75001",
                city="Paris",
            ),
        )

        user = db_session.query(User).filter_by(email="ada@test.fr").one()
        assert user.civility == "F"
        assert user.birthdate == "1815-12-10"
        assert user.city == "Paris"


class TestPolitiqueMotDePasse:
    """La regle qui compte est celle du serveur : un client peut ignorer le front."""

    @pytest.mark.parametrize(
        "faible",
        [
            "password123",  # figure dans les listes d'attaque
            "aaaaaaaaaaaa",  # trop repetitif
            "abcd123456789",  # suite de touches
            "court",  # trop court
        ],
    )
    def test_mot_de_passe_faible_refuse(self, client, faible):
        res = client.post("/auth/register", json=register_payload(password=faible))
        assert res.status_code == 422, f"{faible!r} aurait du etre refuse"

    def test_mot_de_passe_reprenant_le_nom_refuse(self, client):
        res = client.post(
            "/auth/register",
            json=register_payload(name="Lovelace", password="Lovelace2026x"),
        )
        assert res.status_code == 422


class TestConnexion:
    def test_connexion_valide(self, client, user_factory):
        user_factory(email="ada@test.fr")

        res = client.post("/auth/login", json=login_payload("ada@test.fr", BON_MOT_DE_PASSE))

        assert res.status_code == 200, res.text
        assert res.json()["user"]["email"] == "ada@test.fr"

    def test_mauvais_mot_de_passe(self, client, user_factory):
        user_factory(email="ada@test.fr")

        res = client.post("/auth/login", json=login_payload("ada@test.fr", "fauxMotDePasse1"))
        assert res.status_code == 401

    def test_compte_inexistant(self, client):
        res = client.post("/auth/login", json=login_payload("fantome@test.fr", "xyzxyzxyz1"))
        assert res.status_code == 401

    def test_message_identique_pour_ne_pas_reveler_l_existence_du_compte(
        self, client, user_factory
    ):
        """Un message different permettrait d'enumerer les comptes existants."""
        user_factory(email="ada@test.fr")

        compte_existant = client.post(
            "/auth/login", json=login_payload("ada@test.fr", "fauxMotDePasse1")
        )
        compte_inconnu = client.post(
            "/auth/login", json=login_payload("fantome@test.fr", "fauxMotDePasse1")
        )

        assert compte_existant.json()["detail"] == compte_inconnu.json()["detail"]


class TestAntiRobots:
    """Les trois barrieres de app/antibot.py, verifiees une par une."""

    def test_pot_de_miel_rempli_refuse(self, client):
        bloc = solve_antibot("register")
        bloc["honeypot"] = "http://spam.example"

        res = client.post("/auth/register", json=register_payload(antibot=bloc))
        assert res.status_code == 400

    def test_signature_falsifiee_refusee(self, client):
        bloc = solve_antibot("register")
        bloc["signature"] = "0" * 64

        res = client.post("/auth/register", json=register_payload(antibot=bloc))
        assert res.status_code == 400

    def test_preuve_de_travail_invalide_refusee(self, client):
        bloc = solve_antibot("register")
        # Reponse dont on a verifie qu'elle echoue, plutot qu'une chaine
        # arbitraire : a la difficulte abaissee des tests, n'importe quelle
        # valeur passe une fois sur seize, et le test echouait au hasard.
        bloc["nonce"] = wrong_nonce(bloc["salt"], settings.POW_DIFFICULTY)

        res = client.post("/auth/register", json=register_payload(antibot=bloc))
        assert res.status_code == 400

    def test_defi_rejoue_refuse(self, client):
        """Un meme defi ne doit pas servir deux fois."""
        bloc = solve_antibot("register")

        premier = client.post("/auth/register", json=register_payload(antibot=bloc))
        assert premier.status_code == 201

        second = client.post(
            "/auth/register", json=register_payload(email="autre@test.fr", antibot=bloc)
        )
        assert second.status_code == 400

    def test_defi_d_un_autre_usage_refuse(self, client):
        """Une preuve obtenue pour l'inscription ne doit pas servir a se connecter."""
        res = client.post(
            "/auth/register", json=register_payload(antibot=solve_antibot("login"))
        )
        assert res.status_code == 400

    def test_envoi_trop_rapide_refuse(self, client, monkeypatch):
        """Un formulaire renvoye instantanement n'a pas ete saisi par une personne."""
        monkeypatch.setattr(settings, "MIN_FORM_SECONDS", 5.0)

        res = client.post("/auth/register", json=register_payload())
        assert res.status_code == 400

    def test_defi_expire_refuse(self, client, monkeypatch):
        monkeypatch.setattr(settings, "POW_TTL_SECONDS", 0)
        bloc = solve_antibot("register")
        time.sleep(0.05)

        res = client.post("/auth/register", json=register_payload(antibot=bloc))
        assert res.status_code == 400

    def test_usage_inconnu_refuse(self, client):
        assert client.get("/security/challenge?purpose=nimportequoi").status_code == 400

    def test_defi_delivre_pour_un_usage_valide(self, client):
        res = client.get("/security/challenge?purpose=register")
        assert res.status_code == 200
        body = res.json()
        assert body["salt"] and body["signature"]
        assert body["purpose"] == "register"


class TestLimitationDesEchecs:
    """Le comptage par e-mail couvre le bourrage distribue sur plusieurs IP."""

    def test_trop_d_echecs_bloque_temporairement(self, client, user_factory):
        user_factory(email="ada@test.fr")

        for _ in range(antibot.MAX_FAILURES):
            res = client.post("/auth/login", json=login_payload("ada@test.fr", "fauxMotDePasse1"))
            assert res.status_code == 401

        bloque = client.post("/auth/login", json=login_payload("ada@test.fr", BON_MOT_DE_PASSE))
        assert bloque.status_code == 429
        assert "Retry-After" in bloque.headers

    def test_une_connexion_reussie_remet_le_compteur_a_zero(self, client, user_factory):
        user_factory(email="ada@test.fr")

        for _ in range(antibot.MAX_FAILURES - 1):
            client.post("/auth/login", json=login_payload("ada@test.fr", "fauxMotDePasse1"))

        ok = client.post("/auth/login", json=login_payload("ada@test.fr", BON_MOT_DE_PASSE))
        assert ok.status_code == 200

        # Le compteur etant repart de zero, un nouvel echec ne bloque pas.
        res = client.post("/auth/login", json=login_payload("ada@test.fr", "fauxMotDePasse1"))
        assert res.status_code == 401


class TestRoutesProtegees:
    def test_me_sans_jeton(self, client):
        assert client.get("/auth/me").status_code == 401

    def test_me_avec_jeton_valide(self, client, auth_header):
        headers, user = auth_header(email="ada@test.fr")

        res = client.get("/auth/me", headers=headers)

        assert res.status_code == 200
        assert res.json()["email"] == "ada@test.fr"

    def test_jeton_bidon_rejete(self, client):
        res = client.get("/auth/me", headers={"Authorization": "Bearer nimportequoi"})
        assert res.status_code == 401

    def test_jeton_signe_avec_une_autre_cle_rejete(self, client, user_factory):
        """Un jeton force ailleurs ne doit pas ouvrir de session."""
        import jwt

        user, _ = user_factory()
        faux = jwt.encode({"sub": str(user.id)}, "mauvaise-cle", algorithm="HS256")

        res = client.get("/auth/me", headers={"Authorization": f"Bearer {faux}"})
        assert res.status_code == 401

    def test_jeton_expire_rejete(self, client, user_factory):
        from datetime import datetime, timedelta, timezone

        import jwt

        user, _ = user_factory()
        expire = jwt.encode(
            {"sub": str(user.id), "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        res = client.get("/auth/me", headers={"Authorization": f"Bearer {expire}"})
        assert res.status_code == 401
