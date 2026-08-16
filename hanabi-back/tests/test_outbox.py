"""File d'attente des courriels.

Ce qui est verifie ici tient en une phrase : une commande passee produit un
courriel, quoi qu'il arrive au relais - et une panne du relais ne peut pas
faire echouer un achat deja paye.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app import mailer, models, outbox
from app.models import as_utc
from app.config import settings

from test_orders import checkout_payload


class TestDepot:
    def test_une_commande_inscrit_un_courriel(self, client, db_session, product):
        client.post("/orders/checkout", json=checkout_payload(product.id))

        message = db_session.query(models.OutboxEmail).one()
        assert message.destinataire == "client@test.fr"
        assert message.statut == "en_attente"
        assert message.tentatives == 0

    def test_le_courriel_partage_le_sort_de_la_commande(self, client, db_session, product):
        """C'est tout le motif : meme transaction, donc meme destin.

        Le paiement echoue apres l'inscription du courriel dans la session. Si
        les deux ne partageaient pas la transaction, il resterait ici un
        courriel de confirmation pour une commande qui n'existe pas.
        """
        charge = checkout_payload(product.id)
        charge["payment_token"] = "tok_refus"

        client.post("/orders/checkout", json=charge)

        assert db_session.query(models.Order).count() == 0
        assert db_session.query(models.OutboxEmail).count() == 0

    def test_le_courriel_porte_le_detail_de_la_commande(self, client, db_session, product):
        client.post("/orders/checkout", json=checkout_payload(product.id, qty=2))

        message = db_session.query(models.OutboxEmail).one()
        commande = db_session.query(models.Order).one()
        assert commande.number in message.sujet
        assert "Bol de test" in message.texte
        # Version HTML presente, mais jamais seule : un message HTML sans
        # equivalent texte part au courrier indesirable chez bien des filtres.
        assert message.html and message.texte


class TestRemise:
    def test_un_message_du_est_remis(self, client, db_session, product, boite_courriels):
        client.post("/orders/checkout", json=checkout_payload(product.id))

        bilan = outbox.traiter_lot(db_session)

        assert bilan["envoyes"] == 1
        assert len(boite_courriels.boite) == 1
        message = db_session.query(models.OutboxEmail).one()
        assert message.statut == "envoye"
        assert message.envoye_le is not None

    def test_un_message_deja_envoye_n_est_pas_repris(self, client, db_session, product, boite_courriels):
        client.post("/orders/checkout", json=checkout_payload(product.id))
        outbox.traiter_lot(db_session)
        boite_courriels.vider()

        bilan = outbox.traiter_lot(db_session)

        assert bilan["envoyes"] == 0
        assert boite_courriels.boite == []

    def test_un_message_pas_encore_du_attend(self, db_session):
        # `deposer` ne valide pas - c'est le coeur du motif - et la session est
        # en `autoflush=False` : sans ce commit, la ligne n'existe pour personne.
        outbox.deposer(db_session, "a@b.fr", "sujet", "texte")
        db_session.commit()

        message = db_session.query(models.OutboxEmail).one()
        message.prochaine_tentative = datetime.now(timezone.utc) + timedelta(minutes=10)
        db_session.commit()

        assert outbox.traiter_lot(db_session)["envoyes"] == 0


class TestEchecs:
    @pytest.fixture
    def relais_muet(self, monkeypatch):
        """Un relais qui refuse tout."""

        class Muet:
            def envoyer(self, courriel):
                raise ConnectionError("relais injoignable")

        monkeypatch.setattr(mailer, "expediteur", Muet())

    def test_un_echec_differe_au_lieu_de_perdre(self, db_session, relais_muet):
        outbox.deposer(db_session, "a@b.fr", "sujet", "texte")
        db_session.commit()

        bilan = outbox.traiter_lot(db_session)

        assert bilan["echecs"] == 1
        message = db_session.query(models.OutboxEmail).one()
        assert message.statut == "en_attente"
        assert message.tentatives == 1
        assert "ConnectionError" in message.derniere_erreur
        # Reporte dans le futur : sans cela le tour suivant le reprendrait
        # immediatement, en boucle serree.
        # `as_utc` : SQLite ne conserve pas le fuseau, la valeur relue est naive.
        assert as_utc(message.prochaine_tentative) > datetime.now(timezone.utc)

    def test_les_delais_s_allongent_a_chaque_echec(self, db_session, relais_muet):
        outbox.deposer(db_session, "a@b.fr", "sujet", "texte")
        db_session.commit()
        message = db_session.query(models.OutboxEmail).one()

        attentes = []
        for _ in range(3):
            instant = datetime.now(timezone.utc)
            message.prochaine_tentative = instant
            db_session.commit()
            outbox.traiter_lot(db_session, maintenant=instant)
            attentes.append((as_utc(message.prochaine_tentative) - instant).total_seconds())

        # Croissance stricte malgre la dispersion de 20 % : les paliers sont
        # espaces d'un facteur deux, la dispersion ne peut pas les croiser.
        assert attentes[0] < attentes[1] < attentes[2]

    def test_un_message_est_abandonne_apres_le_plafond(self, db_session, relais_muet):
        outbox.deposer(db_session, "a@b.fr", "sujet", "texte")
        db_session.commit()
        message = db_session.query(models.OutboxEmail).one()

        for _ in range(settings.OUTBOX_TENTATIVES_MAX):
            message.prochaine_tentative = datetime.now(timezone.utc)
            db_session.commit()
            outbox.traiter_lot(db_session)

        assert message.statut == "abandonne"
        assert message.tentatives == settings.OUTBOX_TENTATIVES_MAX
        # Abandonne signifie sorti de la file : le tour suivant ne le voit plus.
        assert outbox.traiter_lot(db_session) == {"envoyes": 0, "echecs": 0, "abandons": 0}

    def test_un_relais_en_panne_ne_casse_pas_la_commande(self, client, db_session, product, relais_muet):
        """La raison d'etre de toute la file d'attente.

        Le relais est muet, mais la commande passe : l'achat ne depend plus
        d'un tiers.
        """
        res = client.post("/orders/checkout", json=checkout_payload(product.id))

        assert res.status_code == 201
        assert db_session.query(models.Order).count() == 1

    def test_un_message_en_echec_n_empeche_pas_les_autres(self, db_session, monkeypatch):
        """Un destinataire invalide ne doit pas bloquer la file entiere."""

        class Selectif:
            def __init__(self):
                self.recus = []

            def envoyer(self, courriel):
                if courriel.destinataire == "casse@b.fr":
                    raise ValueError("adresse refusee")
                self.recus.append(courriel)

        selectif = Selectif()
        monkeypatch.setattr(mailer, "expediteur", selectif)

        outbox.deposer(db_session, "casse@b.fr", "sujet", "texte")
        outbox.deposer(db_session, "bon@b.fr", "sujet", "texte")
        db_session.commit()

        bilan = outbox.traiter_lot(db_session)

        assert bilan == {"envoyes": 1, "echecs": 1, "abandons": 0}
        assert [c.destinataire for c in selectif.recus] == ["bon@b.fr"]


class TestMessageConstruit:
    def test_le_message_porte_texte_et_html(self, db_session):
        courriel = mailer.Courriel(
            destinataire="a@b.fr", sujet="Sujet", texte="brut", html="<p>riche</p>"
        )
        msg = courriel.construire()

        assert msg["To"] == "a@b.fr"
        assert msg["Subject"] == "Sujet"
        assert msg.is_multipart()
        types = {part.get_content_type() for part in msg.walk()}
        assert {"text/plain", "text/html"} <= types

    def test_l_expediteur_vient_de_la_configuration(self, db_session):
        msg = mailer.Courriel(destinataire="a@b.fr", sujet="S", texte="t").construire()
        assert settings.MAIL_FROM in msg["From"]
