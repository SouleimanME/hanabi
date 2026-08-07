"""Tarification et codes promo.

C'est le coeur de la regle de securite du projet : le client peut envoyer
n'importe quel montant, seul le calcul serveur fait foi. Ces tests verifient
que les prix viennent bien de la base et que les codes promo sont valides
cote serveur.
"""
from app.pricing import FREE_SHIPPING_THRESHOLD_CENTS, SHIPPING_CENTS


def quote(client, items, promo_code=None):
    res = client.post("/orders/quote", json={"items": items, "promo_code": promo_code})
    return res


class TestSousTotal:
    def test_le_prix_vient_de_la_base_pas_du_client(self, client, product):
        """Le client n'envoie qu'un identifiant et une quantite, jamais un prix."""
        res = quote(client, [{"product_id": product.id, "qty": 2}])

        assert res.status_code == 200
        body = res.json()
        assert body["subtotal_cents"] == 4000  # 2 x 20,00 EUR
        assert body["lines"][0]["unit_price_cents"] == product.price_cents

    def test_produit_inexistant_rejete(self, client):
        res = quote(client, [{"product_id": 9999, "qty": 1}])
        assert res.status_code == 404

    def test_produit_desactive_rejete(self, client, db_session, product):
        product.active = False
        db_session.commit()

        res = quote(client, [{"product_id": product.id, "qty": 1}])
        assert res.status_code == 404

    def test_panier_vide_rejete(self, client):
        assert quote(client, []).status_code == 400

    def test_quantite_negative_rejetee_par_le_schema(self, client, product):
        res = quote(client, [{"product_id": product.id, "qty": -3}])
        assert res.status_code == 422


class TestFraisDePort:
    def test_port_facture_sous_le_seuil(self, client, product):
        body = quote(client, [{"product_id": product.id, "qty": 1}]).json()

        assert body["subtotal_cents"] < FREE_SHIPPING_THRESHOLD_CENTS
        assert body["shipping_cents"] == SHIPPING_CENTS
        assert body["total_cents"] == 2000 + SHIPPING_CENTS

    def test_port_offert_au_dessus_du_seuil(self, client, expensive_product):
        body = quote(client, [{"product_id": expensive_product.id, "qty": 1}]).json()

        assert body["subtotal_cents"] >= FREE_SHIPPING_THRESHOLD_CENTS
        assert body["shipping_cents"] == 0
        assert body["total_cents"] == 9000

    def test_une_remise_peut_faire_repasser_sous_le_seuil(
        self, client, db_session, expensive_product
    ):
        """Regle metier : le port offert s'apprecie APRES remise.

        90 EUR - 20 % = 72 EUR, soit sous le seuil de 80 EUR : le port
        redevient payant.
        """
        from app.models import Promo

        db_session.add(Promo(code="MOINS20", kind="percent", percent=20, active=True))
        db_session.commit()

        body = quote(client, [{"product_id": expensive_product.id, "qty": 1}], "MOINS20").json()

        assert body["discount_cents"] == 1800
        assert body["shipping_cents"] == SHIPPING_CENTS
        assert body["total_cents"] == 9000 - 1800 + SHIPPING_CENTS


class TestCodesPromo:
    def test_remise_en_pourcentage(self, client, product, promos):
        body = quote(client, [{"product_id": product.id, "qty": 5}], "MOINS10").json()

        assert body["subtotal_cents"] == 10000
        assert body["discount_cents"] == 1000
        assert body["promo"]["code"] == "MOINS10"

    def test_remise_en_montant_fixe(self, client, product, promos):
        body = quote(client, [{"product_id": product.id, "qty": 1}], "MOINS5EUR").json()

        assert body["discount_cents"] == 500

    def test_remise_fixe_plafonnee_au_sous_total(self, client, db_session, product):
        """Un code de 50 EUR sur un panier de 20 EUR ne doit pas rendre d'argent."""
        from app.models import Promo

        db_session.add(Promo(code="ENORME", kind="fixed", amount_cents=5000, active=True))
        db_session.commit()

        body = quote(client, [{"product_id": product.id, "qty": 1}], "ENORME").json()

        assert body["discount_cents"] == 2000
        assert body["total_cents"] >= 0

    def test_port_offert(self, client, product, promos):
        body = quote(client, [{"product_id": product.id, "qty": 1}], "PORTOFFERT").json()

        assert body["shipping_cents"] == 0
        assert body["discount_cents"] == 0

    def test_code_inconnu_rejete(self, client, product):
        res = quote(client, [{"product_id": product.id, "qty": 1}], "NIMPORTEQUOI")
        assert res.status_code == 422

    def test_code_desactive_rejete(self, client, product, promos):
        res = quote(client, [{"product_id": product.id, "qty": 1}], "PERIME")
        assert res.status_code == 422

    def test_code_expire_rejete(self, client, db_session, product):
        from datetime import datetime, timedelta, timezone

        from app.models import Promo

        db_session.add(
            Promo(
                code="HIER",
                kind="percent",
                percent=30,
                active=True,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        db_session.commit()

        res = quote(client, [{"product_id": product.id, "qty": 1}], "HIER")
        assert res.status_code == 422
        assert "expir" in res.json()["detail"].lower()

    def test_minimum_de_panier_non_atteint(self, client, product, promos):
        """GROSPANIER exige 100 EUR ; le panier n'en fait que 20."""
        res = quote(client, [{"product_id": product.id, "qty": 1}], "GROSPANIER")
        assert res.status_code == 422

    def test_minimum_de_panier_atteint(self, client, product, promos):
        res = quote(client, [{"product_id": product.id, "qty": 5}], "GROSPANIER")

        assert res.status_code == 200
        assert res.json()["discount_cents"] == 2000  # 20 % de 100 EUR

    def test_code_insensible_a_la_casse_et_aux_espaces(self, client, product, promos):
        body = quote(client, [{"product_id": product.id, "qty": 1}], "  moins5eur  ").json()
        assert body["discount_cents"] == 500


class TestEndpointValidation:
    """POST /promos/validate : verifie un code sans creer de commande."""

    def test_code_valide(self, client, promos):
        res = client.post("/promos/validate", json={"code": "MOINS10", "subtotal_cents": 5000})

        assert res.status_code == 200
        assert res.json()["kind"] == "percent"

    def test_code_invalide(self, client):
        res = client.post("/promos/validate", json={"code": "FAUX", "subtotal_cents": 5000})
        assert res.status_code == 422
