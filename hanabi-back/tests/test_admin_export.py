"""Export CSV des commandes : acces reserve, et format lisible par un tableur."""
import csv
import io


def checkout_payload(product_id, qty=1, email="client@test.fr"):
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
        "promo_code": None,
    }


def read_csv(body: bytes) -> list[dict]:
    """Relit l'export comme le ferait un tableur."""
    # utf-8-sig retire le BOM ajoute pour Excel.
    text = body.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


class TestAccesReserve:
    def test_sans_jeton_refuse(self, client):
        assert client.get("/admin/orders.csv").status_code == 401

    def test_jeton_invalide_refuse(self, client):
        res = client.get("/admin/orders.csv", headers={"Authorization": "Bearer bidon"})
        assert res.status_code == 401

    def test_client_non_admin_refuse(self, client, auth_header):
        """Un compte ordinaire ne doit pas pouvoir aspirer la liste des clients."""
        headers, _ = auth_header(email="curieux@test.fr", is_admin=False)

        res = client.get("/admin/orders.csv", headers=headers)
        assert res.status_code == 403


class TestFormat:
    def test_entetes_de_telechargement(self, client, auth_header):
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)

        res = client.get("/admin/orders.csv", headers=headers)

        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert "attachment" in res.headers["content-disposition"]
        assert ".csv" in res.headers["content-disposition"]

    def test_bom_utf8_present(self, client, auth_header):
        """Sans BOM, Excel en configuration francaise casse les accents."""
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)

        res = client.get("/admin/orders.csv", headers=headers)
        assert res.content.startswith(b"\xef\xbb\xbf")

    def test_une_ligne_par_article(self, client, auth_header, product, expensive_product):
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)
        client.post(
            "/orders/checkout",
            json={
                "items": [
                    {"product_id": product.id, "qty": 2},
                    {"product_id": expensive_product.id, "qty": 1},
                ],
                "email": "acheteur@test.fr",
                "shipping": {
                    "prenom": "Ada",
                    "nom": "Lovelace",
                    "adresse": "12 rue des Tests",
                    "cp": "75001",
                    "ville": "Paris",
                },
                "promo_code": None,
            },
        )

        rows = read_csv(client.get("/admin/orders.csv", headers=headers).content)

        assert len(rows) == 2, "une commande de deux references donne deux lignes"
        # Le numero de commande sert de cle de regroupement dans le tableur.
        assert len({r["numero"] for r in rows}) == 1

    def test_montants_avec_virgule_decimale(self, client, auth_header, product):
        """Un point decimal serait lu comme du texte par un tableur francais."""
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)
        client.post("/orders/checkout", json=checkout_payload(product.id, qty=2))

        rows = read_csv(client.get("/admin/orders.csv", headers=headers).content)

        assert rows[0]["prix_unitaire_eur"] == "20,00"
        assert rows[0]["total_ligne_eur"] == "40,00"

    def test_filtre_par_statut(self, client, auth_header, product):
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)
        client.post("/orders/checkout", json=checkout_payload(product.id))

        paid = read_csv(client.get("/admin/orders.csv?status=paid", headers=headers).content)
        shipped = read_csv(client.get("/admin/orders.csv?status=shipped", headers=headers).content)

        assert len(paid) == 1
        assert shipped == []

    def test_les_separateurs_dans_les_donnees_ne_decalent_pas_les_colonnes(
        self, client, auth_header, db_session
    ):
        """Un nom de produit contenant un point-virgule casserait le tableau."""
        from app.models import Product

        piege = Product(
            code="TST-003",
            name="Bol ; special",
            category="Tradition",
            blurb="Nom piege.",
            price_cents=1500,
            stock=5,
            active=True,
            art="enso,#224A3F,#E4D7BF",
        )
        db_session.add(piege)
        db_session.commit()
        db_session.refresh(piege)

        headers, _ = auth_header(email="patron@test.fr", is_admin=True)
        client.post("/orders/checkout", json=checkout_payload(piege.id))

        rows = read_csv(client.get("/admin/orders.csv", headers=headers).content)

        assert rows[0]["produit"] == "Bol ; special"
        assert rows[0]["quantite"] == "1"
