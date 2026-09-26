"""Fiches multilingues : traductions en base, repli champ par champ, back-office."""
import json

import pytest

from app.models import Product
from app.translations import localize


def _produit(**traductions):
    return Product(
        code="TST-201", name="Lampe Lune", category="Luminaires", blurb="Seize couleurs",
        price_cents=7200, stock=3, active=True, alt="Sphère blanche éclairée",
        traductions=json.dumps(traductions),
    )


@pytest.fixture
def admin_headers(auth_header):
    headers, _ = auth_header(email="admin@test.fr", is_admin=True)
    return headers


@pytest.fixture
def lampe(db_session):
    p = _produit(en={"name": "Moon Lamp", "blurb": "Sixteen colours", "usages": "Night light for a child's room"})
    db_session.add(p)
    db_session.commit()
    return p


def test_le_francais_reste_le_francais():
    assert localize(_produit(en={"name": "Moon Lamp"}), "fr") == (
        "Lampe Lune", "Seize couleurs", "Sphère blanche éclairée"
    )


def test_chaque_champ_retombe_sur_l_anglais_puis_le_francais():
    p = _produit(en={"name": "Moon Lamp", "blurb": "Sixteen colours"}, es={"name": "Lámpara Luna"})
    # Nom espagnol, accroche anglaise, texte alternatif français
    assert localize(p, "es") == ("Lámpara Luna", "Sixteen colours", "Sphère blanche éclairée")


def test_des_traductions_illisibles_ne_cassent_pas_la_fiche():
    p = _produit()
    p.traductions = "pas du json"
    assert localize(p, "en") == ("Lampe Lune", "Seize couleurs", "Sphère blanche éclairée")


def test_la_boutique_affiche_la_fiche_traduite(client, lampe):
    fiche = client.get(f"/products/{lampe.id}", params={"lang": "en"}).json()
    assert (fiche["name"], fiche["blurb"]) == ("Moon Lamp", "Sixteen colours")
    assert fiche["alt"] == "Sphère blanche éclairée"
    assert "traductions" not in fiche


def test_un_usage_traduit_se_cherche_dans_sa_langue(client, lampe):
    trouves = client.get("/products", params={"q": "night light", "lang": "en"}).json()
    assert [p["code"] for p in trouves] == ["TST-201"]


def test_le_back_office_remplace_une_langue_sans_toucher_l_autre(client, admin_headers, lampe):
    reponse = client.patch(
        f"/admin/products/{lampe.id}",
        json={"traductions": {"es": {"name": "Lámpara Luna", "blurb": "Dieciséis colores"}}},
        headers=admin_headers,
    )
    assert reponse.status_code == 200
    traductions = reponse.json()["traductions"]
    assert traductions["en"]["name"] == "Moon Lamp"
    assert traductions["es"]["blurb"] == "Dieciséis colores"


def test_une_langue_inconnue_est_refusee(client, admin_headers, lampe):
    reponse = client.patch(
        f"/admin/products/{lampe.id}", json={"traductions": {"de": {"name": "Mondlampe"}}},
        headers=admin_headers,
    )
    assert reponse.status_code == 422


def test_un_texte_alternatif_trop_long_est_refuse(client, admin_headers, lampe):
    reponse = client.patch(f"/admin/products/{lampe.id}", json={"alt": "x" * 301}, headers=admin_headers)
    assert reponse.status_code == 422


def test_un_objet_cree_avec_ses_traductions(client, admin_headers):
    reponse = client.post("/admin/products", headers=admin_headers, json={
        "code": "TST-202", "name": "Bol Enso", "category": "Décoration", "blurb": "Céramique",
        "price_cents": 2400, "stock": 4, "alt": "Bol noir sur fond clair",
        "traductions": {"en": {"name": "Enso Bowl", "blurb": "Ceramic"}},
    })
    assert reponse.status_code == 201
    fiche = client.get(f"/products/{reponse.json()['id']}", params={"lang": "es"}).json()
    # Pas d'espagnol : l'anglais d'abord
    assert fiche["name"] == "Enso Bowl"


def test_le_catalogue_de_depart_est_traduit_en_base(client, db_session):
    from app.seed import seed

    seed(db_session)
    fiche = client.get("/products", params={"q": "HNB-078", "lang": "es"}).json()[0]
    assert fiche["name"] == "Estampa La Gran Ola"
