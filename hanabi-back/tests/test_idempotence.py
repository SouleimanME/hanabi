"""Rejeu du tunnel d'achat.

Ce que ces tests protegent : un acheteur qui clique deux fois, un navigateur qui
rejoue apres une coupure, un telephone qui reessaie sur delai depasse. Dans les
trois cas la meme intention arrive deux fois, et une seule commande doit en
sortir.
"""
import pytest

from app import models
from app.idempotency import EN_TETE

from test_orders import checkout_payload


CLE = "idem-test-0000000000000001"


class TestRejeu:
    def test_la_meme_cle_ne_cree_qu_une_commande(self, client, db_session, product):
        charge = checkout_payload(product.id, qty=1)

        premiere = client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})
        seconde = client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})

        assert premiere.status_code == 201
        assert seconde.status_code == 201
        # Meme numero de commande : c'est la reponse de la premiere qui est
        # rejouee, pas une seconde commande qui lui ressemble.
        assert premiere.json()["number"] == seconde.json()["number"]
        assert db_session.query(models.Order).count() == 1

    def test_le_rejeu_ne_reprend_pas_de_stock(self, client, db_session, product):
        depart = product.stock
        charge = checkout_payload(product.id, qty=2)

        client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})
        client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})

        db_session.refresh(product)
        assert product.stock == depart - 2

    def test_le_rejeu_ne_produit_pas_un_second_courriel(self, client, db_session, product):
        charge = checkout_payload(product.id)

        client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})
        client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})

        assert db_session.query(models.OutboxEmail).count() == 1

    def test_le_rejeu_est_annonce_dans_les_en_tetes(self, client, product):
        """Le corps est identique : seul l'en-tete distingue les deux cas."""
        charge = checkout_payload(product.id)

        premiere = client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})
        seconde = client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})

        assert premiere.headers["Idempotent-Replay"] == "false"
        assert seconde.headers["Idempotent-Replay"] == "true"

    def test_deux_cles_differentes_font_deux_commandes(self, client, db_session, product):
        """Le garde-fou ne doit pas empecher un second achat volontaire."""
        charge = checkout_payload(product.id)

        client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})
        client.post("/orders/checkout", json=charge, headers={EN_TETE: "idem-test-0000000000000002"})

        assert db_session.query(models.Order).count() == 2

    def test_sans_cle_le_comportement_reste_celui_d_avant(self, client, db_session, product):
        """L'en-tete est facultatif : les clients existants continuent de marcher."""
        charge = checkout_payload(product.id)

        client.post("/orders/checkout", json=charge)
        client.post("/orders/checkout", json=charge)

        assert db_session.query(models.Order).count() == 2


class TestCleReutilisee:
    def test_meme_cle_corps_different_est_refusee(self, client, db_session, product):
        """Renvoyer la reponse d'un autre achat serait le pire comportement :
        le client croirait sa commande passee."""
        client.post("/orders/checkout", json=checkout_payload(product.id, qty=1), headers={EN_TETE: CLE})
        res = client.post(
            "/orders/checkout", json=checkout_payload(product.id, qty=2), headers={EN_TETE: CLE}
        )

        assert res.status_code == 422
        assert db_session.query(models.Order).count() == 1

    def test_l_ordre_des_cles_json_n_est_pas_une_difference(self, client, db_session, product):
        """Deux serialisations du meme corps doivent avoir la meme empreinte.

        Sans tri des cles, un client honnete verrait son reessai refuse pour
        « corps different » selon l'ordre choisi par sa bibliotheque HTTP.
        """
        charge = checkout_payload(product.id)
        inverse = dict(reversed(list(charge.items())))

        client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})
        res = client.post("/orders/checkout", json=inverse, headers={EN_TETE: CLE})

        assert res.status_code == 201
        assert db_session.query(models.Order).count() == 1


class TestFormeDeLaCle:
    @pytest.mark.parametrize("cle", ["court", "x" * 200, "avec espace", "point.virgule;"])
    def test_cle_malformee_refusee(self, client, product, cle):
        res = client.post(
            "/orders/checkout", json=checkout_payload(product.id), headers={EN_TETE: cle}
        )
        assert res.status_code == 400

    def test_cle_vide_traitee_comme_absente(self, client, db_session, product):
        res = client.post(
            "/orders/checkout", json=checkout_payload(product.id), headers={EN_TETE: "   "}
        )
        assert res.status_code == 201


class TestPaiement:
    """Le paiement est simule, mais ses chemins d'echec sont jouables.

    C'est ce qui donne son sens a l'idempotence : rejouer une insertion est
    benin, rejouer un debit ne l'est pas.
    """

    def test_carte_refusee_annule_tout(self, client, db_session, product):
        depart = product.stock
        charge = checkout_payload(product.id)
        charge["payment_token"] = "tok_refus"

        res = client.post("/orders/checkout", json=charge)

        assert res.status_code == 402
        db_session.refresh(product)
        # Le stock est rendu par l'annulation de la transaction : pris avant le
        # paiement, il ne doit pas rester reserve sur un refus.
        assert product.stock == depart
        assert db_session.query(models.Order).count() == 0
        assert db_session.query(models.OutboxEmail).count() == 0

    def test_issue_indecise_conserve_la_commande_en_attente(self, client, db_session, product):
        """Un delai depasse ne dit pas si le debit a eu lieu.

        On ne peut ni confirmer - livrer un paiement non prouve - ni annuler -
        oublier un debit possible et rendre un stock peut-etre deja vendu. La
        commande reste donc en attente de rapprochement.
        """
        charge = checkout_payload(product.id)
        charge["payment_token"] = "tok_indecis"

        res = client.post("/orders/checkout", json=charge)

        assert res.status_code == 202
        commande = db_session.query(models.Order).one()
        assert commande.status == "pending"
        assert commande.payment_ref is None
        # Rien a confirmer tant que le paiement n'est pas etabli.
        assert db_session.query(models.OutboxEmail).count() == 0

    def test_le_stock_reste_retenu_sur_une_issue_indecise(self, client, db_session, product):
        """Le rendre reviendrait a revendre un article peut-etre deja paye."""
        depart = product.stock
        charge = checkout_payload(product.id, qty=2)
        charge["payment_token"] = "tok_indecis"

        client.post("/orders/checkout", json=charge)

        db_session.refresh(product)
        assert product.stock == depart - 2

    def test_le_rejeu_d_une_issue_indecise_ne_double_pas_la_commande(
        self, client, db_session, product
    ):
        """LE cas qui justifie tout le mecanisme.

        Une premiere version annulait la transaction sur issue indecise en
        invitant a reessayer avec la meme cle. C'etait une promesse creuse : le
        `rollback` emportait aussi la ligne d'idempotence, qui vit dans la meme
        transaction. La cle disparaissait, le reessai repartait de zero, et le
        second debit qu'on pretendait empecher redevenait possible.
        """
        charge = checkout_payload(product.id)
        charge["payment_token"] = "tok_indecis"

        premiere = client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})
        seconde = client.post("/orders/checkout", json=charge, headers={EN_TETE: CLE})

        assert premiere.status_code == 202
        assert seconde.status_code == 202
        assert premiere.json()["number"] == seconde.json()["number"]
        assert db_session.query(models.Order).count() == 1

    def test_la_reference_d_autorisation_est_conservee(self, client, db_session, product):
        """Sans elle, rien ne rapproche une commande d'un mouvement bancaire."""
        client.post("/orders/checkout", json=checkout_payload(product.id))

        commande = db_session.query(models.Order).first()
        assert commande.payment_ref
        assert commande.payment_ref.startswith("auth_")
