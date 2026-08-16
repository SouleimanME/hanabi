"""Courriels de compte : confirmation d'adresse, mot de passe oublie, newsletter.

Les jetons ne sont jamais lus depuis la reponse HTTP - ils n'y figurent pas, et
c'est voulu. On les extrait du courriel depose en file, exactement comme le
ferait la personne qui releve sa boite. Un test qui recevrait le jeton dans la
reponse validerait une API que la production n'expose pas.
"""
import re

import pytest

from app import models, tokens

from antibot_helper import solve_antibot


def _jeton_du_dernier_courriel(db_session, motif=r"jeton=([\w-]+)"):
    message = (
        db_session.query(models.OutboxEmail)
        .order_by(models.OutboxEmail.id.desc())
        .first()
    )
    assert message is not None, "aucun courriel n'a ete depose"
    trouve = re.search(motif, message.texte)
    assert trouve, f"aucun jeton dans le courriel :\n{message.texte[:400]}"
    return trouve.group(1)


def _inscription(client, email="nouvelle@hanabi.fr", password="Correct-Cheval-Pile-9"):
    return client.post(
        "/auth/register",
        json={
            "name": "Ada Lovelace",
            "email": email,
            "password": password,
            "antibot": solve_antibot("register"),
        },
    )


class TestConfirmationAdresse:
    def test_l_inscription_depose_un_courriel(self, client, db_session):
        res = _inscription(client)

        assert res.status_code == 201
        message = db_session.query(models.OutboxEmail).one()
        assert message.destinataire == "nouvelle@hanabi.fr"
        assert "confirme" in message.sujet.lower()

    def test_le_compte_nait_non_confirme(self, client, db_session):
        _inscription(client)

        compte = db_session.query(models.User).filter_by(email="nouvelle@hanabi.fr").one()
        assert compte.email_verified is False

    def test_le_lien_confirme_l_adresse(self, client, db_session):
        _inscription(client)
        jeton = _jeton_du_dernier_courriel(db_session)

        res = client.post("/auth/verify-email", json={"jeton": jeton})

        assert res.status_code == 200
        assert res.json()["email_verified"] is True

    def test_le_compte_est_utilisable_sans_confirmation(self, client):
        """Bloquer la connexion transformerait un courriel tombe dans les
        indesirables en compte inaccessible."""
        _inscription(client)

        res = client.post(
            "/auth/login",
            json={
                "email": "nouvelle@hanabi.fr",
                "password": "Correct-Cheval-Pile-9",
                "antibot": solve_antibot("login"),
            },
        )
        assert res.status_code == 200

    def test_un_jeton_ne_sert_qu_une_fois(self, client, db_session):
        _inscription(client)
        jeton = _jeton_du_dernier_courriel(db_session)

        assert client.post("/auth/verify-email", json={"jeton": jeton}).status_code == 200
        assert client.post("/auth/verify-email", json={"jeton": jeton}).status_code == 400

    def test_un_jeton_invente_est_refuse(self, client):
        res = client.post("/auth/verify-email", json={"jeton": "x" * 43})
        assert res.status_code == 400

    def test_un_nouveau_lien_revoque_le_precedent(self, client, db_session):
        """Demander un nouveau lien doit invalider l'ancien : sinon un lien
        intercepte reste utilisable alors qu'on le croit remplace."""
        res = _inscription(client)
        premier = _jeton_du_dernier_courriel(db_session)
        jeton_acces = res.json()["access_token"]

        client.post(
            "/auth/resend-verification", headers={"Authorization": f"Bearer {jeton_acces}"}
        )
        second = _jeton_du_dernier_courriel(db_session)

        assert premier != second
        assert client.post("/auth/verify-email", json={"jeton": premier}).status_code == 400
        assert client.post("/auth/verify-email", json={"jeton": second}).status_code == 200

    def test_renvoyer_a_un_compte_deja_confirme_ne_fait_rien(self, client, db_session):
        res = _inscription(client)
        acces = res.json()["access_token"]
        client.post("/auth/verify-email", json={"jeton": _jeton_du_dernier_courriel(db_session)})
        avant = db_session.query(models.OutboxEmail).count()

        res = client.post(
            "/auth/resend-verification", headers={"Authorization": f"Bearer {acces}"}
        )

        assert res.json()["deja_confirmee"] is True
        assert db_session.query(models.OutboxEmail).count() == avant

    def test_renvoyer_exige_d_etre_connecte(self, client):
        """Ouverte, la route permettrait d'inonder la boite de tout inscrit."""
        assert client.post("/auth/resend-verification").status_code in (401, 403)


class TestMotDePasseOublie:
    @pytest.fixture
    def compte(self, client):
        _inscription(client)
        return "nouvelle@hanabi.fr"

    def test_un_lien_est_envoye(self, client, db_session, compte):
        db_session.query(models.OutboxEmail).delete()
        db_session.commit()

        res = client.post("/auth/forgot-password", json={"email": compte})

        assert res.status_code == 202
        message = db_session.query(models.OutboxEmail).one()
        assert "mot de passe" in message.sujet.lower()

    def test_une_adresse_inconnue_recoit_la_meme_reponse(self, client, db_session):
        """Sans cela, le formulaire devient un detecteur d'adresses : on teste
        une liste entiere et on en extrait les clients de la boutique."""
        connue = client.post("/auth/forgot-password", json={"email": "nouvelle@hanabi.fr"})
        inconnue = client.post("/auth/forgot-password", json={"email": "personne@hanabi.fr"})

        assert connue.status_code == inconnue.status_code == 202
        assert connue.json() == inconnue.json()

    def test_aucun_courriel_pour_une_adresse_inconnue(self, client, db_session):
        client.post("/auth/forgot-password", json={"email": "personne@hanabi.fr"})
        assert db_session.query(models.OutboxEmail).count() == 0

    def test_le_lien_change_le_mot_de_passe(self, client, db_session, compte):
        client.post("/auth/forgot-password", json={"email": compte})
        jeton = _jeton_du_dernier_courriel(db_session)

        res = client.post(
            "/auth/reset-password", json={"jeton": jeton, "password": "Nouveau-Passe-Robuste-42"}
        )

        assert res.status_code == 200
        # Connecte dans la foulee : renvoyer vers la connexion apres avoir
        # prouve son identite serait une etape de trop.
        assert res.json()["access_token"]

        ancien = client.post(
            "/auth/login",
            json={"email": compte, "password": "Correct-Cheval-Pile-9",
                  "antibot": solve_antibot("login")},
        )
        assert ancien.status_code == 401

    def test_le_lien_ne_sert_qu_une_fois(self, client, db_session, compte):
        client.post("/auth/forgot-password", json={"email": compte})
        jeton = _jeton_du_dernier_courriel(db_session)

        premier = client.post(
            "/auth/reset-password", json={"jeton": jeton, "password": "Nouveau-Passe-Robuste-42"}
        )
        second = client.post(
            "/auth/reset-password", json={"jeton": jeton, "password": "Encore-Un-Autre-Passe-7"}
        )

        assert premier.status_code == 200
        assert second.status_code == 400

    def test_un_mot_de_passe_refuse_ne_brule_pas_le_lien(self, client, db_session, compte):
        """Sinon un premier essai trop court obligerait a repartir de la boite."""
        client.post("/auth/forgot-password", json={"email": compte})
        jeton = _jeton_du_dernier_courriel(db_session)

        faible = client.post("/auth/reset-password", json={"jeton": jeton, "password": "abc"})
        assert faible.status_code == 422

        bon = client.post(
            "/auth/reset-password", json={"jeton": jeton, "password": "Nouveau-Passe-Robuste-42"}
        )
        assert bon.status_code == 200

    def test_la_reinitialisation_confirme_l_adresse(self, client, db_session, compte):
        """Reprendre la main prouve l'acces a la boite."""
        client.post("/auth/forgot-password", json={"email": compte})
        jeton = _jeton_du_dernier_courriel(db_session)

        res = client.post(
            "/auth/reset-password", json={"jeton": jeton, "password": "Nouveau-Passe-Robuste-42"}
        )

        assert res.json()["user"]["email_verified"] is True

    def test_un_jeton_de_confirmation_ne_reinitialise_pas(self, client, db_session):
        """Les usages sont cloisonnes : un jeton vaut pour ce qu'il a ete emis.

        Sans cette separation, le lien de confirmation - valable sept jours et
        envoye a toute inscription - deviendrait un lien de changement de mot
        de passe.
        """
        _inscription(client)
        jeton = _jeton_du_dernier_courriel(db_session)

        res = client.post(
            "/auth/reset-password", json={"jeton": jeton, "password": "Nouveau-Passe-Robuste-42"}
        )
        assert res.status_code == 400


class TestStockageDesJetons:
    def test_le_jeton_n_est_jamais_stocke_en_clair(self, client, db_session):
        """Une copie de la base ne doit donner aucun lien exploitable."""
        _inscription(client)
        jeton = _jeton_du_dernier_courriel(db_session)

        ligne = db_session.query(models.Token).one()
        assert ligne.empreinte != jeton
        assert len(ligne.empreinte) == 64  # SHA-256 en hexadecimal

    def test_l_empreinte_correspond_bien_au_jeton(self, client, db_session):
        _inscription(client)
        jeton = _jeton_du_dernier_courriel(db_session)

        assert tokens.consommer(db_session, jeton, tokens.VERIFICATION) is not None

    def test_les_durees_different_selon_l_usage(self):
        """Confirmer une adresse peut attendre ; reinitialiser donne acces au
        compte et doit se refermer vite."""
        assert tokens.DUREES[tokens.REINITIALISATION] < tokens.DUREES[tokens.VERIFICATION]


class TestNewsletter:
    def test_l_inscription_envoie_le_code(self, client, db_session):
        res = client.post(
            "/newsletter/subscribe",
            json={"email": "curieux@hanabi.fr", "lang": "fr",
                  "antibot": solve_antibot("subscribe")},
        )

        assert res.status_code == 201
        message = db_session.query(models.OutboxEmail).one()
        assert message.destinataire == "curieux@hanabi.fr"
        # Le code reste aussi dans la reponse : il s'affiche a l'ecran dans la
        # foulee, le courriel est un double pour le retrouver plus tard.
        code = res.json()["code"]
        if code:
            assert code in message.texte

    def test_une_reinscription_n_envoie_pas_un_second_courriel(self, client, db_session):
        """Sinon ce formulaire ouvert permet d'inonder la boite de quiconque."""
        for _ in range(3):
            client.post(
                "/newsletter/subscribe",
                json={"email": "curieux@hanabi.fr", "lang": "fr",
                      "antibot": solve_antibot("subscribe")},
            )

        assert db_session.query(models.OutboxEmail).count() == 1
