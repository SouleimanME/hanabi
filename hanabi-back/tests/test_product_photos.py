"""Photos produit : le visuel principal doit accepter une vraie image.

Le champ `art` recoit soit un motif court « forme,couleur1,couleur2 », soit une
photo en data URI base64 de plusieurs centaines de kilo-octets. Il etait borne a
60 caracteres, cote schema comme cote colonne : enregistrer une fiche illustree
echouait, et commander ce produit aurait echoue aussi.
"""
import pytest

from app.routers.admin import ART_MAX_LENGTH

# Un carre de 1200 px encode en base64 pese environ 700 000 caracteres.
PHOTO = "data:image/jpeg;base64," + "A" * 700_000
MOTIF = "enso,#E0382A,#16140F"


def fiche(**extra):
    data = {
        "code": "TST-PH",
        "name": "Fiche photo",
        "category": "Collection",
        "blurb": "Fiche de test.",
        "price_cents": 1000,
        "stock": 3,
    }
    data.update(extra)
    return data


class TestVisuelPrincipal:
    def test_une_photo_est_acceptee(self, client, auth_header):
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)

        res = client.post("/admin/products", json=fiche(art=PHOTO), headers=headers)

        assert res.status_code == 201, res.text
        assert res.json()["art"] == PHOTO

    def test_la_photo_est_relue_intacte(self, client, auth_header):
        """Une troncature silencieuse donnerait une image illisible."""
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)
        pid = client.post("/admin/products", json=fiche(art=PHOTO), headers=headers).json()["id"]

        relu = client.get(f"/admin/products/{pid}", headers=headers).json()

        assert relu["art"] == PHOTO
        assert len(relu["art"]) == len(PHOTO)

    def test_le_motif_court_fonctionne_toujours(self, client, auth_header):
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)

        res = client.post("/admin/products", json=fiche(art=MOTIF), headers=headers)

        assert res.status_code == 201
        assert res.json()["art"] == MOTIF

    def test_la_modification_accepte_aussi_une_photo(self, client, auth_header, product):
        """Sans borne sur le PATCH, la modification serait un contournement."""
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)

        res = client.patch(f"/admin/products/{product.id}", json={"art": PHOTO}, headers=headers)

        assert res.status_code == 200
        assert res.json()["art"] == PHOTO

    def test_un_champ_demesure_reste_refuse(self, client, auth_header):
        """La borne demeure : un seul champ ne doit pas absorber tout le corps."""
        headers, _ = auth_header(email="patron@test.fr", is_admin=True)
        enorme = "data:image/jpeg;base64," + "A" * (ART_MAX_LENGTH + 1)

        res = client.post("/admin/products", json=fiche(art=enorme), headers=headers)

        assert res.status_code == 422


class TestCommandeAvecPhoto:
    def test_commander_un_produit_illustre(self, client, db_session, auth_header):
        """`OrderItem.art` copie le visuel : il devait aussi accepter une photo."""
        from app.models import Product

        headers, _ = auth_header(email="patron@test.fr", is_admin=True)
        pid = client.post(
            "/admin/products", json=fiche(art=PHOTO, stock=5), headers=headers
        ).json()["id"]
        db_session.get(Product, pid)

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
        assert res.json()["items"][0]["art"] == PHOTO


class TestLimiteDeCorps:
    @pytest.mark.parametrize(
        "taille_mo,attendu",
        [(3.5, False), (7.5, False), (9.0, True)],
        ids=["3.5 Mo passe", "7.5 Mo passe", "9 Mo refuse"],
    )
    def test_seuil(self, client, taille_mo, attendu):
        """Une fiche illustree pese plusieurs mega-octets une fois encodee.

        L'ancien plafond d'un mega-octet la refusait avec « Requete trop
        volumineuse », avant meme d'atteindre la validation.
        """
        charge = {
            "items": [{"product_id": 1, "qty": 1}],
            "promo_code": None,
            "_pad": "x" * int(taille_mo * 1_000_000),
        }

        res = client.post("/orders/quote", json=charge)

        assert (res.status_code == 413) is attendu


# --------------------------------------------------------------------------
# Suggestions issues de l'entrepot decisionnel
# --------------------------------------------------------------------------


def test_affinites_sans_entrepot_rendent_une_liste_vide(client, product):
    """Sur SQLite, la route repond 200 avec une liste vide, jamais une erreur.

    C'est la garantie qui compte : la fiche produit doit rester consultable
    quand l'entrepot n'existe pas - developpement local, schemas non
    construits, base neuve. Une rubrique de recommandations absente est un
    moindre mal ; une fiche cassee, non.
    """
    reponse = client.get(f"/products/{product.id}/affinites")

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_affinites_bornent_le_nombre_de_suggestions(client, product):
    """Au-dela de six, ce n'est plus une suggestion mais un second catalogue."""
    assert client.get(f"/products/{product.id}/affinites?limit=7").status_code == 422
    assert client.get(f"/products/{product.id}/affinites?limit=0").status_code == 422
