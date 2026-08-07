"""Mesure d'audience et indicateurs decisionnels du back-office."""
import pytest

from antibot_helper import solve_antibot

from app.models import ProductView


def checkout_payload(product_id, qty=1, email="client@test.fr"):
    """Meme forme que dans `test_orders` : le schema exige l'adresse de livraison."""
    return {
        "items": [{"product_id": product_id, "qty": qty}],
        "email": email,
        "shipping": {
            "prenom": "Ada",
            "nom": "Lovelace",
            "adresse": "12 rue des Machines",
            "cp": "75011",
            "ville": "Paris",
        },
        "promo_code": None,
    }


@pytest.fixture
def admin_headers(auth_header):
    headers, _ = auth_header(email="patron@hanabi.fr", is_admin=True)
    return headers


class TestMesureDesVues:
    def test_enregistre_une_consultation(self, client, db_session, product):
        res = client.post(f"/products/{product.id}/view")

        assert res.status_code == 204
        assert db_session.query(ProductView).filter_by(product_id=product.id).count() == 1

    def test_rattache_la_vue_au_compte_connecte(self, client, db_session, product, auth_header):
        headers, user = auth_header()

        client.post(f"/products/{product.id}/view", headers=headers)

        vue = db_session.query(ProductView).one()
        assert vue.user_id == user.id

    def test_visiteur_anonyme(self, client, db_session, product):
        """Sans compte, la ligne ne doit designer personne."""
        client.post(f"/products/{product.id}/view")

        assert db_session.query(ProductView).one().user_id is None

    def test_produit_inconnu_ne_leve_pas_d_erreur(self, client, db_session):
        """Une mesure d'usage ne doit pas faire echouer la navigation."""
        res = client.post("/products/99999/view")

        assert res.status_code == 204
        assert db_session.query(ProductView).count() == 0


class TestAnalytics:
    def test_reserve_aux_administrateurs(self, client, auth_header):
        headers, _ = auth_header(email="client@test.fr", is_admin=False)

        assert client.get("/admin/analytics", headers=headers).status_code == 403
        assert client.get("/admin/analytics").status_code == 401

    def test_base_vide_ne_casse_pas(self, client, admin_headers):
        """Aucune division par zero sur une boutique qui n'a rien vendu."""
        res = client.get("/admin/analytics", headers=admin_headers)

        assert res.status_code == 200, res.text
        corps = res.json()
        assert corps["kpis"]["conversion"] == 0.0
        assert corps["kpis"]["aov_cents"] == 0
        assert corps["kpis"]["repeat_rate"] == 0.0

    def test_serie_mensuelle_continue(self, client, admin_headers):
        """Un mois sans activite doit apparaitre a zero, pas disparaitre."""
        res = client.get("/admin/analytics?months=6", headers=admin_headers)

        serie = res.json()["series"]
        assert len(serie) == 6
        assert all(m["revenue_cents"] == 0 for m in serie)
        # Ordonnee du plus ancien au plus recent.
        assert serie == sorted(serie, key=lambda m: m["month"])

    def test_conversion_rapporte_commandes_et_vues(
        self, client, db_session, product, admin_headers
    ):
        # Quatre consultations, une commande : 25 % de conversion.
        for _ in range(4):
            client.post(f"/products/{product.id}/view")
        commande = client.post(
            "/orders/checkout",
            json=checkout_payload(product.id, qty=2, email="acheteur@test.fr"),
        )
        assert commande.status_code == 201, commande.text

        fiche = next(
            p for p in client.get("/admin/analytics", headers=admin_headers).json()["products"]
            if p["id"] == product.id
        )

        assert fiche["views"] == 4
        assert fiche["orders"] == 1
        # Deux exemplaires vendus, mais une seule commande : la conversion se
        # calcule sur les commandes, pas sur les unites.
        assert fiche["units"] == 2
        assert fiche["conversion"] == 0.25
        assert fiche["revenue_cents"] == 2 * product.price_cents

    def test_produit_jamais_commande_reste_liste(self, client, product, admin_headers):
        """Le fond de catalogue est justement ce que l'on cherche a reperer."""
        fiches = client.get("/admin/analytics", headers=admin_headers).json()["products"]

        fiche = next(p for p in fiches if p["id"] == product.id)
        assert fiche["orders"] == 0
        assert fiche["conversion"] == 0.0
        assert fiche["last_order_at"] is None

    def test_commande_annulee_hors_du_chiffre_d_affaires(
        self, client, product, admin_headers
    ):
        res = client.post(
            "/orders/checkout", json=checkout_payload(product.id, email="annule@test.fr")
        )
        numero = res.json()["number"]
        client.patch(f"/admin/orders/{numero}/status?status=cancelled", headers=admin_headers)

        kpis = client.get("/admin/analytics", headers=admin_headers).json()["kpis"]

        assert kpis["orders"] == 0
        assert kpis["revenue_cents"] == 0

    def test_commande_expediee_compte_dans_le_chiffre_d_affaires(
        self, client, product, admin_headers
    ):
        """Une commande partie a bien ete encaissee.

        Ne retenir que le statut « payee » faisait baisser le chiffre d'affaires
        a mesure que les colis quittaient l'atelier.
        """
        res = client.post(
            "/orders/checkout", json=checkout_payload(product.id, email="expedie@test.fr")
        )
        numero = res.json()["number"]
        client.patch(f"/admin/orders/{numero}/status?status=shipped", headers=admin_headers)

        kpis = client.get("/admin/analytics", headers=admin_headers).json()["kpis"]

        assert kpis["orders"] == 1
        assert kpis["revenue_cents"] > 0


class TestListeClients:
    def test_paginee(self, client, user_factory, admin_headers):
        for i in range(5):
            user_factory(email=f"client{i}@test.fr")

        res = client.get("/admin/users?limit=2&offset=0", headers=admin_headers)

        corps = res.json()
        assert corps["total"] == 6  # cinq clients plus l'administrateur
        assert len(corps["items"]) == 2

    def test_recherche_sur_le_nom_l_email_et_la_ville(
        self, client, db_session, user_factory, admin_headers
    ):
        user, _ = user_factory(email="marie.dupont@test.fr", name="Marie Dupont")
        user.city = "Bordeaux"
        db_session.commit()

        par_nom = client.get("/admin/users?q=marie", headers=admin_headers).json()
        par_ville = client.get("/admin/users?q=bordeaux", headers=admin_headers).json()
        sans_reponse = client.get("/admin/users?q=zzzz", headers=admin_headers).json()

        assert par_nom["total"] == 1
        assert par_ville["total"] == 1
        assert sans_reponse["total"] == 0

    def test_agrege_l_historique_d_achat(self, client, product, auth_header, admin_headers):
        headers, _ = auth_header(email="fidele@test.fr")
        for _ in range(2):
            res = client.post(
                "/orders/checkout",
                headers=headers,
                json=checkout_payload(product.id, email="fidele@test.fr"),
            )
            assert res.status_code == 201, res.text

        liste = client.get("/admin/users?q=fidele", headers=admin_headers).json()["items"]

        assert liste[0]["order_count"] == 2
        assert liste[0]["total_spent_cents"] == 2 * (product.price_cents + 690)
