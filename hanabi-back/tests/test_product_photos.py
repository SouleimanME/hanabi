"""Photos produit : une vraie image est acceptée, rangée à part et servie en cache."""
import base64
import re

import pytest

from app import models
from app.routers.admin import ART_MAX_LENGTH

# Un carre de 1200 px encode en base64 pese environ 700 000 caracteres.
PHOTO = "data:image/jpeg;base64," + "A" * 700_000
OCTETS = base64.b64decode("A" * 700_000)
MOTIF = "enso,#E0382A,#16140F"
ADRESSE = re.compile(r"^http://testserver/media/([0-9a-f]{64})$")


def fiche(**extra):
    data = {
        "code": "TST-PH",
        "name": "Fiche photo",
        "category": "Figurines",
        "blurb": "Fiche de test.",
        "price_cents": 1000,
        "stock": 3,
    }
    data.update(extra)
    return data


@pytest.fixture
def patron(auth_header):
    headers, _ = auth_header(email="patron@test.fr", is_admin=True)
    return headers


def _octets(client, adresse):
    return client.get(adresse.replace("http://testserver", ""))


class TestVisuelPrincipal:
    def test_une_photo_est_rangee_a_part(self, client, patron, db_session):
        res = client.post("/admin/products", json=fiche(art=PHOTO, images=[PHOTO]), headers=patron)

        assert res.status_code == 201, res.text
        corps = res.json()
        assert ADRESSE.match(corps["art"]), corps["art"]
        assert corps["images"] == [corps["art"]]
        # En base, la fiche ne garde que le chemin court ; la photo est rangée une fois
        produit = db_session.get(models.Product, corps["id"])
        assert produit.art.startswith("/media/")
        assert db_session.query(models.Media).count() == 1

    def test_la_photo_est_relue_intacte(self, client, patron):
        """Une troncature silencieuse donnerait une image illisible."""
        adresse = client.post("/admin/products", json=fiche(art=PHOTO), headers=patron).json()["art"]

        reponse = _octets(client, adresse)

        assert reponse.status_code == 200
        assert reponse.content == OCTETS
        assert reponse.headers["content-type"] == "image/jpeg"

    def test_le_catalogue_ne_transporte_plus_les_photos(self, client, patron):
        client.post("/admin/products", json=fiche(art=PHOTO, images=[PHOTO]), headers=patron)

        catalogue = client.get("/products").text

        assert "data:" not in catalogue
        assert len(catalogue) < 10_000

    def test_une_adresse_renvoyee_telle_quelle_ne_duplique_rien(self, client, patron, db_session):
        """Le formulaire renvoie les adresses qu'il a reçues."""
        corps = client.post("/admin/products", json=fiche(art=PHOTO, images=[PHOTO]), headers=patron).json()

        res = client.patch(
            f"/admin/products/{corps['id']}",
            json={"art": corps["art"], "images": corps["images"], "name": "Renommée"},
            headers=patron,
        )

        assert res.status_code == 200
        assert res.json()["art"] == corps["art"]
        assert db_session.get(models.Product, corps["id"]).art.startswith("/media/")
        assert db_session.query(models.Media).count() == 1

    def test_le_motif_court_fonctionne_toujours(self, client, patron):
        res = client.post("/admin/products", json=fiche(art=MOTIF), headers=patron)

        assert res.status_code == 201
        assert res.json()["art"] == MOTIF

    def test_la_modification_accepte_aussi_une_photo(self, client, patron, product):
        res = client.patch(f"/admin/products/{product.id}", json={"art": PHOTO}, headers=patron)

        assert res.status_code == 200
        assert _octets(client, res.json()["art"]).content == OCTETS

    def test_un_format_inconnu_est_refuse(self, client, patron):
        res = client.post("/admin/products", json=fiche(art="data:image/gif;base64,R0lGOD"), headers=patron)

        assert res.status_code == 422
        assert "PNG, JPEG ou WebP" in res.text

    def test_un_champ_demesure_reste_refuse(self, client, patron):
        """La borne demeure : un seul champ ne doit pas absorber tout le corps."""
        enorme = "data:image/jpeg;base64," + "A" * (ART_MAX_LENGTH + 1)

        res = client.post("/admin/products", json=fiche(art=enorme), headers=patron)

        assert res.status_code == 422


class TestServiceDesPhotos:
    def test_en_cache_un_an_et_affichable_ailleurs(self, client, patron):
        adresse = client.post("/admin/products", json=fiche(art=PHOTO), headers=patron).json()["art"]

        reponse = _octets(client, adresse)

        assert "immutable" in reponse.headers["cache-control"]
        assert "max-age=31536000" in reponse.headers["cache-control"]
        # La boutique est servie par un autre site que l'API
        assert reponse.headers["cross-origin-resource-policy"] == "cross-origin"

    def test_deja_en_cache_rien_ne_repart(self, client, patron):
        adresse = client.post("/admin/products", json=fiche(art=PHOTO), headers=patron).json()["art"]
        etag = _octets(client, adresse).headers["etag"]

        reponse = client.get(adresse.replace("http://testserver", ""), headers={"If-None-Match": etag})

        assert reponse.status_code == 304
        assert reponse.content == b""

    def test_le_json_reste_reserve_au_meme_site(self, client):
        assert client.get("/products").headers["cross-origin-resource-policy"] == "same-site"

    def test_une_photo_inconnue(self, client):
        assert client.get("/media/" + "0" * 64).status_code == 404
        assert client.get("/media/pas-une-empreinte").status_code == 422


class TestCommandeAvecPhoto:
    def test_commander_un_produit_illustre(self, client, patron):
        """`OrderItem.art` copie le visuel : la commande garde l'adresse de la photo."""
        pid = client.post(
            "/admin/products", json=fiche(art=PHOTO, stock=5), headers=patron
        ).json()["id"]

        res = client.post(
            "/orders/checkout",
            json={
                "items": [{"product_id": pid, "qty": 1}],
                "email": "client@test.fr",
                "shipping": {
                    "prenom": "Ada",
                    "nom": "Lovelace",
                    "adresse": "12 rue des Tests",
                    "cp": "75001",
                    "ville": "Paris",
                },
                "cgv_acceptees": True,
                "promo_code": None,
            },
        )

        assert res.status_code == 201, res.text
        assert _octets(client, res.json()["items"][0]["art"]).content == OCTETS

class TestLimiteDeCorps:
    @pytest.mark.parametrize(
        "taille_mo,attendu",
        [(3.5, False), (7.5, False), (9.0, True)],
        ids=["3.5 Mo passe", "7.5 Mo passe", "9 Mo refuse"],
    )
    def test_seuil(self, client, taille_mo, attendu):
        """Une fiche illustree pese plusieurs mega-octets une fois encodee."""
        charge = {
            "items": [{"product_id": 1, "qty": 1}],
            "promo_code": None,
            "_pad": "x" * int(taille_mo * 1_000_000),
        }

        res = client.post("/orders/quote", json=charge)

        assert (res.status_code == 413) is attendu


# --- Suggestions issues de l'entrepot decisionnel ---


def test_affinites_sans_entrepot_rendent_une_liste_vide(client, product):
    """Sur SQLite, la route repond 200 avec une liste vide, jamais une erreur."""
    reponse = client.get(f"/products/{product.id}/affinites")

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_affinites_bornent_le_nombre_de_suggestions(client, product):
    """Au-dela de six, ce n'est plus une suggestion mais un second catalogue."""
    assert client.get(f"/products/{product.id}/affinites?limit=7").status_code == 422
    assert client.get(f"/products/{product.id}/affinites?limit=0").status_code == 422
