"""Inscription aux annonces de series et offre de bienvenue."""
from app.models import Promo, Subscriber


def subscribe(client, antibot_for, email="visiteur@test.fr", lang="fr"):
    return client.post(
        "/newsletter/subscribe",
        json={"email": email, "lang": lang, "antibot": antibot_for("subscribe")},
    )


class TestInscription:
    def test_enregistre_l_adresse_et_renvoie_le_code(self, client, db_session, antibot_for):
        db_session.add(Promo(code="BIENVENUE10", kind="percent", percent=10, active=True))
        db_session.commit()

        res = subscribe(client, antibot_for)

        assert res.status_code == 201, res.text
        assert res.json() == {"ok": True, "code": "BIENVENUE10"}
        assert db_session.query(Subscriber).filter_by(email="visiteur@test.fr").count() == 1

    def test_adresse_normalisee_en_minuscules(self, client, db_session, antibot_for):
        subscribe(client, antibot_for, email="Visiteur@Test.FR")
        assert db_session.query(Subscriber).filter_by(email="visiteur@test.fr").count() == 1

    def test_deuxieme_inscription_sans_doublon_ni_erreur(self, client, db_session, antibot_for):
        # Repondre « deja inscrite » revelerait la presence d'une adresse dans
        # la base a quiconque la saisit : la reponse doit etre indistinguable.
        first = subscribe(client, antibot_for)
        second = subscribe(client, antibot_for)

        assert first.status_code == second.status_code == 201
        assert first.json() == second.json()
        assert db_session.query(Subscriber).count() == 1

    def test_reinscription_apres_desinscription(self, client, db_session, antibot_for):
        db_session.add(Subscriber(email="revenu@test.fr", unsubscribed=True))
        db_session.commit()

        subscribe(client, antibot_for, email="revenu@test.fr")

        db_session.expire_all()
        again = db_session.query(Subscriber).filter_by(email="revenu@test.fr").one()
        assert again.unsubscribed is False

    def test_email_invalide_refuse(self, client, db_session, antibot_for):
        res = subscribe(client, antibot_for, email="pas-une-adresse")

        assert res.status_code == 422
        assert db_session.query(Subscriber).count() == 0


class TestOffreDeBienvenue:
    def test_pas_de_code_annonce_si_le_promo_n_existe_pas(self, client, antibot_for):
        # L'inscription reste valable : c'est la remise qui n'est pas promise.
        res = subscribe(client, antibot_for)

        assert res.status_code == 201
        assert res.json()["code"] is None

    def test_pas_de_code_annonce_si_le_promo_est_desactive(
        self, client, db_session, antibot_for
    ):
        db_session.add(Promo(code="BIENVENUE10", kind="percent", percent=10, active=False))
        db_session.commit()

        assert subscribe(client, antibot_for).json()["code"] is None


class TestBarrieres:
    def test_preuve_anti_robot_exigee(self, client, db_session):
        res = client.post(
            "/newsletter/subscribe",
            json={"email": "robot@test.fr", "lang": "fr", "antibot": {}},
        )

        assert res.status_code == 422
        assert db_session.query(Subscriber).count() == 0

    def test_preuve_d_un_autre_usage_refusee(self, client, db_session, antibot_for):
        # Un defi obtenu pour l'inscription au compte ne doit pas ouvrir la
        # porte de la newsletter.
        res = client.post(
            "/newsletter/subscribe",
            json={"email": "robot@test.fr", "lang": "fr", "antibot": antibot_for("register")},
        )

        assert res.status_code == 400
        assert db_session.query(Subscriber).count() == 0

    def test_pot_de_miel_rempli_refuse(self, client, db_session, antibot_for):
        proof = antibot_for("subscribe")
        proof["honeypot"] = "https://spam.example"

        res = client.post(
            "/newsletter/subscribe",
            json={"email": "robot@test.fr", "lang": "fr", "antibot": proof},
        )

        assert res.status_code == 400
        assert db_session.query(Subscriber).count() == 0

    def test_defi_non_rejouable(self, client, db_session, antibot_for):
        proof = antibot_for("subscribe")
        payload = {"email": "visiteur@test.fr", "lang": "fr", "antibot": proof}

        assert client.post("/newsletter/subscribe", json=payload).status_code == 201
        assert client.post("/newsletter/subscribe", json=payload).status_code == 400
        assert db_session.query(Subscriber).count() == 1
