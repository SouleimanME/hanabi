"""Déclinaisons : une gourde noire à 11,80 €, blanche à 12,74 €, chacune son stock."""
import pytest

from app import models

LIVRAISON = {"prenom": "Ada", "nom": "Lovelace", "adresse": "12 rue des Tests", "cp": "75001", "ville": "Paris"}


@pytest.fixture
def patron(auth_header):
    headers, _ = auth_header(email="patron@test.fr", is_admin=True)
    return headers


def _gourde(client, patron, **extra):
    corps = {
        "code": "TST-GRD", "name": "Gourde isotherme", "category": "Accessoires",
        "blurb": "Inox double paroi", "price_cents": 0, "stock": 0,
        "variantes": [
            {"libelle": "Noir", "couleur": "#111111", "price_cents": 1180, "stock": 5,
             "traductions": {"en": "Black", "es": "Negro"}},
            {"libelle": "Blanc", "couleur": "#F4F1EA", "price_cents": 1274, "stock": 2},
        ],
        **extra,
    }
    res = client.post("/admin/products", json=corps, headers=patron)
    assert res.status_code == 201, res.text
    return res.json()


def _commander(client, lignes):
    return client.post("/orders/checkout", json={
        "items": lignes, "email": "client@test.fr", "shipping": LIVRAISON,
        "cgv_acceptees": True, "promo_code": None,
    })


# --- Fiche ---


def test_prix_et_stock_de_l_objet_viennent_des_declinaisons(client, patron):
    g = _gourde(client, patron)
    # Le prix le plus bas s'affiche « à partir de » ; le stock est la somme
    assert (g["price_cents"], g["stock"]) == (1180, 7)
    assert [v["libelle"] for v in g["variantes"]] == ["Noir", "Blanc"]


def test_la_boutique_montre_les_declinaisons_dans_sa_langue(client, patron):
    g = _gourde(client, patron)
    fiche = client.get(f"/products/{g['id']}", params={"lang": "en"}).json()
    assert [(v["libelle"], v["price_cents"]) for v in fiche["variantes"]] == [("Black", 1180), ("Blanc", 1274)]
    # Sans traduction, le libellé français reste
    assert fiche["variantes"][0]["couleur"] == "#111111"


def test_un_objet_simple_n_a_pas_de_declinaison(client, product):
    assert client.get(f"/products/{product.id}").json()["variantes"] == []


def test_deux_libelles_identiques_sont_refuses(client, patron):
    res = client.post("/admin/products", json={
        "code": "TST-DBL", "name": "Double", "category": "Accessoires", "blurb": "x",
        "price_cents": 0, "stock": 0,
        "variantes": [{"libelle": "Noir", "price_cents": 100, "stock": 1},
                      {"libelle": "noir", "price_cents": 200, "stock": 1}],
    }, headers=patron)
    assert res.status_code == 422


# --- Devis ---


def test_le_devis_prend_le_prix_de_la_declinaison(client, patron):
    g = _gourde(client, patron)
    blanc = g["variantes"][1]["id"]
    devis = client.post("/orders/quote", json={"items": [{"product_id": g["id"], "variante_id": blanc, "qty": 2}]}).json()
    ligne = devis["lines"][0]
    assert (ligne["unit_price_cents"], ligne["variante_libelle"]) == (1274, "Blanc")
    assert devis["subtotal_cents"] == 2548


def test_sans_declinaison_choisie_le_devis_refuse(client, patron):
    g = _gourde(client, patron)
    res = client.post("/orders/quote", json={"items": [{"product_id": g["id"], "qty": 1}]})
    assert res.status_code == 422
    assert "déclinaison" in res.json()["detail"]


def test_la_declinaison_d_un_autre_objet_est_refusee(client, patron, product):
    g = _gourde(client, patron)
    noir = g["variantes"][0]["id"]
    assert client.post("/orders/quote", json={"items": [{"product_id": product.id, "variante_id": noir, "qty": 1}]}).status_code == 422
    autre = _gourde(client, patron, code="TST-GR2")
    res = client.post("/orders/quote", json={"items": [{"product_id": autre["id"], "variante_id": noir, "qty": 1}]})
    assert res.status_code == 404


# --- Commande ---


def test_la_commande_prend_le_stock_de_la_couleur_et_la_retient(client, patron, db_session):
    g = _gourde(client, patron)
    noir, blanc = (v["id"] for v in g["variantes"])
    res = _commander(client, [
        {"product_id": g["id"], "variante_id": noir, "qty": 2},
        {"product_id": g["id"], "variante_id": blanc, "qty": 1},
    ])
    assert res.status_code == 201, res.text
    assert [i["variante_libelle"] for i in res.json()["items"]] == ["Noir", "Blanc"]
    assert res.json()["total_cents"] == 2 * 1180 + 1274 + 690

    db_session.expire_all()
    assert db_session.get(models.Variante, noir).stock == 3
    assert db_session.get(models.Variante, blanc).stock == 1
    assert db_session.get(models.Product, g["id"]).stock == 4


def test_une_couleur_epuisee_ne_se_commande_pas_meme_si_l_autre_reste(client, patron, db_session):
    g = _gourde(client, patron)
    blanc = g["variantes"][1]["id"]
    res = _commander(client, [{"product_id": g["id"], "variante_id": blanc, "qty": 3}])
    assert res.status_code == 409
    assert "Blanc" in res.json()["detail"]
    db_session.expire_all()
    assert db_session.get(models.Product, g["id"]).stock == 7


def test_annuler_rend_le_stock_a_la_couleur(client, patron, db_session):
    g = _gourde(client, patron)
    noir = g["variantes"][0]["id"]
    numero = _commander(client, [{"product_id": g["id"], "variante_id": noir, "qty": 2}]).json()["number"]
    res = client.patch(f"/admin/orders/{numero}/status", params={"status": "cancelled"}, headers=patron)
    assert res.status_code == 200, res.text
    db_session.expire_all()
    assert db_session.get(models.Variante, noir).stock == 5
    assert db_session.get(models.Product, g["id"]).stock == 7


# --- Retrait d'une déclinaison ---


def test_une_declinaison_jamais_commandee_se_supprime(client, patron, db_session):
    g = _gourde(client, patron)
    noir = g["variantes"][0]
    res = client.patch(f"/admin/products/{g['id']}", json={"variantes": [noir]}, headers=patron)
    assert [v["libelle"] for v in res.json()["variantes"]] == ["Noir"]
    assert (res.json()["price_cents"], res.json()["stock"]) == (1180, 5)
    assert db_session.query(models.Variante).filter_by(product_id=g["id"]).count() == 1


def test_une_declinaison_commandee_est_retiree_de_la_vente_pas_effacee(client, patron, db_session):
    g = _gourde(client, patron)
    noir, blanc = g["variantes"]
    _commander(client, [{"product_id": g["id"], "variante_id": blanc["id"], "qty": 1}])
    client.patch(f"/admin/products/{g['id']}", json={"variantes": [noir]}, headers=patron)

    db_session.expire_all()
    retiree = db_session.get(models.Variante, blanc["id"])
    assert retiree is not None and retiree.active is False
    fiche = client.get(f"/products/{g['id']}").json()
    assert [v["libelle"] for v in fiche["variantes"]] == ["Noir"]
    # Retirée, elle ne se commande plus
    res = client.post("/orders/quote", json={"items": [{"product_id": g["id"], "variante_id": blanc["id"], "qty": 1}]})
    assert res.status_code == 404
