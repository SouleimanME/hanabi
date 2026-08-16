"""Commande : decrement de stock, integrite des montants, cloisonnement."""
from app import models


def checkout_payload(product_id, qty=1, email="client@test.fr", promo_code=None):
    return {
        "items": [{"product_id": product_id, "qty": qty}],
        "email": email,
        "shipping": {
            "prenom": "Ada",
            "nom": "Lovelace",
            "adresse": "12 rue des Tests",
            "cp": "75001",
            "ville": "Paris",
        },
        "promo_code": promo_code,
        # Obligatoire depuis l'ajout des conditions de vente. Son absence a fait
        # echouer huit tests d'un coup, ce qui est le comportement voulu : un
        # champ obligatoire qui laisserait passer un appel sans lui ne servirait
        # a rien.
        "cgv_acceptees": True,
    }


class TestCheckout:
    def test_commande_invitee_acceptee(self, client, product):
        res = client.post("/orders/checkout", json=checkout_payload(product.id))

        assert res.status_code == 201
        body = res.json()
        assert body["number"].startswith("ATL")
        assert body["status"] == "paid"

    def test_le_stock_est_decremente(self, client, db_session, product):
        stock_initial = product.stock

        client.post("/orders/checkout", json=checkout_payload(product.id, qty=2))

        db_session.refresh(product)
        assert product.stock == stock_initial - 2

    def test_quantite_au_dela_du_plafond_refusee_par_le_schema(self, client, product):
        """Le schema plafonne a 99 par ligne : au-dela, rejet avant tout acces base.

        Ce plafond evite qu'une commande fabriquee a la main demande un million
        d'unites, ce qui ferait travailler la base pour rien.

        Le cas « quantite valide mais stock insuffisant » est couvert par
        test_commande_au_dela_du_stock_refusee, qui attend un 409.
        """
        res = client.post("/orders/checkout", json=checkout_payload(product.id, qty=100))
        assert res.status_code == 422

    def test_commande_au_dela_du_stock_refusee(self, client, db_session, product):
        res = client.post("/orders/checkout", json=checkout_payload(product.id, qty=6))

        assert res.status_code == 409
        db_session.refresh(product)
        assert product.stock == 5  # inchange

    def test_le_stock_ne_devient_jamais_negatif(self, client, db_session, product):
        """Deux commandes SUCCESSIVES sur le dernier article.

        La seconde doit echouer : le decrement passe par un UPDATE conditionnel
        (`WHERE stock >= qty`), pas par une lecture suivie d'une ecriture.

        Ce test disait « concurrentes », ce qu'il n'a jamais fait : ses deux
        requetes partent l'une apres l'autre. Il verifie le refus sur stock
        insuffisant, ce qui compte, mais ne met jamais deux requetes en vol
        ensemble - or c'est la que se cache l'entrelacement. Le vrai
        parallelisme est teste dans `test_concurrence.py`, avec des fils
        d'execution et une barriere de depart.
        """
        client.post("/orders/checkout", json=checkout_payload(product.id, qty=5))
        seconde = client.post("/orders/checkout", json=checkout_payload(product.id, qty=1))

        assert seconde.status_code == 409
        db_session.refresh(product)
        assert product.stock == 0

    def test_le_prix_paye_est_fige_dans_la_commande(self, client, db_session, product):
        """Une hausse de prix ne doit pas reecrire l'historique des commandes."""
        res = client.post("/orders/checkout", json=checkout_payload(product.id))
        assert res.status_code == 201

        product.price_cents = 9999
        db_session.commit()

        commande = res.json()
        assert commande["items"][0]["unit_price_cents"] == 2000

    def test_les_totaux_de_la_commande_viennent_du_serveur(self, client, product, promos):
        res = client.post("/orders/checkout", json=checkout_payload(product.id, qty=5, promo_code="MOINS10"))

        body = res.json()
        assert body["subtotal_cents"] == 10000
        assert body["discount_cents"] == 1000
        assert body["total_cents"] == body["subtotal_cents"] - body["discount_cents"] + body["shipping_cents"]

    def test_code_promo_invalide_bloque_la_commande(self, client, db_session, product):
        res = client.post("/orders/checkout", json=checkout_payload(product.id, promo_code="FAUX"))

        assert res.status_code == 422
        db_session.refresh(product)
        assert product.stock == 5  # aucun stock consomme

    def test_commande_rattachee_au_compte_connecte(self, client, product, auth_header):
        headers, user = auth_header()

        res = client.post("/orders/checkout", json=checkout_payload(product.id), headers=headers)

        assert res.status_code == 201


class TestHistorique:
    def test_historique_exige_une_connexion(self, client):
        assert client.get("/orders").status_code == 401

    def test_l_historique_ne_montre_que_ses_propres_commandes(
        self, client, product, auth_header
    ):
        alice_headers, _ = auth_header(email="alice@test.fr")
        client.post("/orders/checkout", json=checkout_payload(product.id), headers=alice_headers)

        bob_headers, _ = auth_header(email="bob@test.fr")
        res = client.get("/orders", headers=bob_headers)

        assert res.status_code == 200
        assert res.json() == []

    def test_une_commande_d_autrui_est_introuvable(self, client, product, auth_header):
        """Cloisonnement : connaitre un numero ne suffit pas a lire la commande."""
        alice_headers, _ = auth_header(email="alice@test.fr")
        commande = client.post(
            "/orders/checkout", json=checkout_payload(product.id), headers=alice_headers
        ).json()

        bob_headers, _ = auth_header(email="bob@test.fr")
        res = client.get(f"/orders/{commande['number']}", headers=bob_headers)

        assert res.status_code == 404


class TestConditionsDeVente:
    """Obligatoires en vente a distance, et verifiees COTE SERVEUR.

    Une case a cocher qui ne vit que dans le navigateur se contourne depuis la
    console, et l'acceptation perdrait toute valeur probante.
    """

    def test_une_commande_sans_acceptation_est_refusee(self, client, db_session, product):
        charge = checkout_payload(product.id)
        charge["cgv_acceptees"] = False

        res = client.post("/orders/checkout", json=charge)

        assert res.status_code == 422
        assert db_session.query(models.Order).count() == 0

    def test_le_champ_est_obligatoire(self, client, product):
        """Absent n'est pas « false » : c'est un corps invalide."""
        charge = checkout_payload(product.id)
        del charge["cgv_acceptees"]

        assert client.post("/orders/checkout", json=charge).status_code == 422

    def test_le_refus_precede_toute_ecriture(self, client, db_session, product):
        """Inutile de prendre du stock pour une commande qu'on va rejeter."""
        depart = product.stock
        charge = checkout_payload(product.id)
        charge["cgv_acceptees"] = False

        client.post("/orders/checkout", json=charge)

        db_session.refresh(product)
        assert product.stock == depart

    def test_la_version_acceptee_est_enregistree(self, client, db_session, product):
        """Un booleen dirait qu'une case a ete cochee, pas CE QUI a ete accepte.

        Les conditions evoluent ; sans la version, l'acceptation ne prouve rien.
        """
        from app.config import settings

        client.post("/orders/checkout", json=checkout_payload(product.id))

        commande = db_session.query(models.Order).one()
        assert commande.cgv_version == settings.CGV_VERSION
        assert commande.cgv_acceptees_le is not None
