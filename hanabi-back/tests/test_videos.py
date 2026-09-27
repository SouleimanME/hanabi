"""Vidéos : signature d'envoi vers R2, et ce que le back-office en obtient."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from app import videos
from app.config import settings


def test_la_signature_suit_le_vecteur_publie_par_aws():
    """Exemple « presigned URL » de la documentation SigV4 d'Amazon S3 : une
    erreur d'un octet dans la chaîne canonique changerait la signature."""
    url = videos.presigner(
        "GET", "examplebucket.s3.amazonaws.com", "/test.txt",
        "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "us-east-1",
        datetime(2013, 5, 24, tzinfo=timezone.utc), 86400,
    )
    signature = parse_qs(urlparse(url).query)["X-Amz-Signature"][0]
    assert signature == "aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"


@pytest.fixture
def r2(monkeypatch):
    for nom, valeur in {
        "R2_ACCOUNT_ID": "compte", "R2_ACCESS_KEY_ID": "cle", "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET": "hanabi-videos", "R2_PUBLIC_URL": "https://pub-hanabi.r2.dev/",
    }.items():
        monkeypatch.setattr(settings, nom, valeur)


@pytest.fixture
def patron(auth_header):
    headers, _ = auth_header(email="patron@test.fr", is_admin=True)
    return headers


def test_sans_r2_le_back_office_ne_propose_pas_de_video(client, patron):
    assert client.get("/admin/medias/etat", headers=patron).json()["videos"] is False
    assert client.post("/admin/medias/video", json={"type": "video/mp4", "taille": 10}, headers=patron).status_code == 503


def test_une_autorisation_pour_un_fichier_et_un_type(client, patron, r2):
    corps = client.post(
        "/admin/medias/video", json={"type": "video/mp4", "taille": 5_000_000}, headers=patron
    ).json()
    envoi = urlparse(corps["envoi"])
    assert envoi.netloc == "compte.r2.cloudflarestorage.com"
    assert envoi.path.startswith("/hanabi-videos/videos/") and envoi.path.endswith(".mp4")
    parametres = parse_qs(envoi.query)
    # Le type est signé : un autre fichier ne passerait pas
    assert parametres["X-Amz-SignedHeaders"] == ["content-type;host"]
    assert parametres["X-Amz-Expires"] == ["900"]
    assert corps["entetes"] == {"Content-Type": "video/mp4"}
    # L'adresse publique pointe sur le même fichier
    assert corps["url"] == "https://pub-hanabi.r2.dev" + envoi.path.removeprefix("/hanabi-videos")


@pytest.mark.parametrize("demande", [
    {"type": "image/gif", "taille": 10},
    {"type": "video/mp4", "taille": 300 * 1024 * 1024},
])
def test_un_type_ou_un_poids_hors_limite_est_refuse(client, patron, r2, demande):
    assert client.post("/admin/medias/video", json=demande, headers=patron).status_code == 422


def test_reserve_au_back_office(client, auth_header, r2):
    headers, _ = auth_header()
    assert client.post("/admin/medias/video", json={"type": "video/mp4", "taille": 10}, headers=headers).status_code == 403


def test_les_videos_peuvent_avoir_leur_propre_section(client, patron):
    res = client.post("/admin/products", json={
        "code": "TST-VAP", "name": "Gourde", "category": "Accessoires", "blurb": "x",
        "price_cents": 1000, "stock": 1, "videos_a_part": True,
    }, headers=patron)
    assert res.json()["videos_a_part"] is True
    pid = res.json()["id"]
    assert client.get(f"/products/{pid}").json()["videos_a_part"] is True
    client.patch(f"/admin/products/{pid}", json={"videos_a_part": False}, headers=patron)
    assert client.get(f"/products/{pid}").json()["videos_a_part"] is False


def test_une_video_dans_la_galerie_reste_une_adresse(client, patron):
    video = "https://pub-hanabi.r2.dev/videos/abc.mp4"
    res = client.post("/admin/products", json={
        "code": "TST-VID", "name": "Gourde", "category": "Accessoires", "blurb": "x",
        "price_cents": 1000, "stock": 1, "images": ["enso,#E0382A,#16140F", video],
    }, headers=patron)
    assert res.status_code == 201
    fiche = client.get(f"/products/{res.json()['id']}").json()
    assert video in fiche["images"]
