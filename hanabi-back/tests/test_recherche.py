"""Recherche du catalogue : prix, texte, sens, et ce que l'API en montre."""
import zlib

import numpy as np
import pytest

from app import plongement, recherche
from app.config import settings
from app.models import Product
from app.recherche import Fiche, analyser, chercher, couverture


def _fiche(id, code, nom, accroche, categorie="Figurines", prix=3000, usages=()):
    return Fiche(id, code, categorie, prix, ((nom, accroche),), tuple(usages))


RENARD = _fiche(1, "TST-001", "Figurine Kitsune", "Renard en résine", prix=4800)
LAMPE = _fiche(2, "TST-002", "Lampe Lune", "Seize couleurs", "Luminaires", 7200,
               ["Veilleuse pour une chambre d'enfant"])
BOL = _fiche(3, "TST-003", "Bol Enso", "Céramique émaillée", "Décoration", 2400)
CATALOGUE = [RENARD, LAMPE, BOL]


class EncodeurFactice:
    """Sac de mots haché : deux textes partageant des mots sont proches."""

    def __init__(self):
        self.encodes = 0

    def _vecteur(self, texte):
        v = np.zeros(1024)
        for mot in recherche.mots_utiles(texte.split(":", 1)[-1]):
            v[zlib.crc32(mot.encode()) % 1024] += 1
        return v / (np.linalg.norm(v) or 1)

    def requetes(self, textes):
        return np.array([self._vecteur(t) for t in textes])

    def passages(self, textes):
        self.encodes += len(textes)
        return np.array([self._vecteur(t) for t in textes])


# --- Prix ---


@pytest.mark.parametrize(
    "q, texte, bas, haut",
    [
        ("moins de 30 €", "", None, 3000),
        ("lampe à moins de 70 euros", "lampe a", None, 7000),
        ("figurine under 40", "figurine", None, 4000),
        ("lámpara menos de 50", "lampara", None, 5000),
        ("entre 30 et 40 €", "", 3000, 4000),
        ("de 20 à 35 euros", "", 2000, 3500),
        ("cadeau 30-40€", "cadeau", 3000, 4000),
        ("plus de 60 €", "", 6000, None),
        ("moins de 19,90 €", "", None, 1990),
        # Un nombre sans mot de prix reste du texte : une taille, un code
        ("figurine 15 cm", "figurine 15 cm", None, None),
        ("HNB-021", "hnb-021", None, None),
    ],
)
def test_le_prix_se_lit_dans_la_phrase(q, texte, bas, haut):
    assert analyser(q) == recherche.Requete(texte, bas, haut)


def test_un_budget_seul_rend_les_objets_du_moins_cher_au_plus_cher():
    assert chercher(CATALOGUE, "moins de 50 €") == [BOL.id, RENARD.id]


def test_un_budget_filtre_les_objets_trouves_par_le_texte():
    assert chercher(CATALOGUE, "renard moins de 40 €") == []
    assert chercher(CATALOGUE, "renard moins de 50 €") == [RENARD.id]


# --- Texte ---


@pytest.mark.parametrize(
    "q, attendus",
    [
        ("kitsune", [RENARD.id]),
        ("KITSUNÉ", [RENARD.id]),
        ("kitsun", [RENARD.id]),       # mot en cours de frappe
        ("kitsoune", [RENARD.id]),     # faute de frappe
        ("renard en résine", [RENARD.id]),
        ("veilleuse", [LAMPE.id]),     # lu dans les usages
        ("TST-003", [BOL.id]),
        ("cadeau renard", [RENARD.id]),  # « cadeau » ne restreint rien
        ("pizza", []),
        ("", []),
    ],
)
def test_par_le_texte(q, attendus):
    assert chercher(CATALOGUE, q) == attendus


def test_un_mot_court_ne_vaut_pas_prefixe():
    art = _fiche(4, "TST-004", "Kokeshi", "Artisanat du bois")
    assert couverture(art, "art") == 0.0
    assert couverture(art, "artisan") == 1.0


# --- Sens ---


def test_le_sens_retient_ce_qui_se_detache_du_catalogue(monkeypatch):
    monkeypatch.setattr(recherche, "INDEX", recherche.Index())
    # « couleurs » et « seize » ne sont pas des mots de la requête : seul le
    # sens relie la requête à la lampe
    lampe = _fiche(2, "TST-002", "Lampe Lune", "Lumière douce chambre nuit", "Luminaires", 7200)
    assert chercher([RENARD, lampe, BOL], "lumière de nuit", EncodeurFactice()) == [lampe.id]


def test_le_sens_ne_repond_rien_a_une_requete_hors_catalogue(monkeypatch):
    monkeypatch.setattr(recherche, "INDEX", recherche.Index())
    assert chercher(CATALOGUE, "chargeur de téléphone", EncodeurFactice()) == []


def test_les_correspondances_completes_passent_devant_le_sens(monkeypatch):
    monkeypatch.setattr(recherche, "INDEX", recherche.Index())
    trouves = chercher(CATALOGUE, "lampe", EncodeurFactice())
    assert trouves[0] == LAMPE.id


def test_une_fiche_n_est_encodee_qu_une_fois_tant_qu_elle_ne_change_pas(monkeypatch):
    index = recherche.Index()
    monkeypatch.setattr(recherche, "INDEX", index)
    encodeur = EncodeurFactice()
    chercher(CATALOGUE, "lumière", encodeur)
    premiers = encodeur.encodes
    chercher(CATALOGUE, "renard", encodeur)
    assert encodeur.encodes == premiers

    # Une fiche modifiée est réencodée, et sa version périmée oubliée
    renomme = _fiche(1, "TST-001", "Figurine Kitsune", "Renard blanc en résine", prix=4800)
    chercher([renomme, LAMPE, BOL], "renard", encodeur)
    assert encodeur.encodes == premiers + len(recherche.passages(renomme))
    assert RENARD not in index._cache


def test_sans_modele_le_chargement_ne_casse_rien(monkeypatch, tmp_path):
    monkeypatch.setattr(plongement, "DOSSIER", tmp_path)
    monkeypatch.setattr(plongement, "_encodeur", None)
    assert plongement.encodeur(attendre=True) is None


def test_un_modele_illisible_coupe_le_sens_pas_la_boutique(monkeypatch, tmp_path):
    for nom in plongement.FICHIERS:
        (tmp_path / nom).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / nom).write_bytes(b"abime")
    monkeypatch.setattr(plongement, "DOSSIER", tmp_path)
    monkeypatch.setattr(plongement, "_encodeur", None)
    monkeypatch.setattr(plongement, "_echec", False)
    assert plongement.encodeur(attendre=True) is None
    assert plongement._echec


def test_un_fichier_d_empreinte_inattendue_est_refuse(monkeypatch, tmp_path):
    class Reponse:
        def __init__(self):
            self.lu = False

        def read(self, _):
            if self.lu:
                return b""
            self.lu = True
            return b"autre contenu"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(plongement, "DOSSIER", tmp_path)
    monkeypatch.setattr(plongement.urllib.request, "urlopen", lambda *a, **k: Reponse())
    with pytest.raises(RuntimeError, match="empreinte"):
        plongement.telecharger()
    assert not any(p.is_file() for p in tmp_path.rglob("*"))


# --- API ---


@pytest.fixture
def admin_headers(auth_header):
    headers, _ = auth_header(email="admin@test.fr", is_admin=True)
    return headers


@pytest.fixture
def vitrine(db_session):
    objets = [
        Product(code="TST-101", name="Figurine Kitsune", category="Figurines",
                blurb="Renard en résine", price_cents=4800, stock=3, active=True,
                usages="Cadeau pour un amateur de yokai"),
        Product(code="TST-102", name="Lampe Lune", category="Luminaires",
                blurb="Seize couleurs", price_cents=7200, stock=3, active=True,
                usages="Veilleuse pour une chambre d'enfant"),
        Product(code="TST-103", name="Masque Kitsune", category="Décoration",
                blurb="Renard peint main", price_cents=3900, stock=3, active=True),
    ]
    db_session.add_all(objets)
    db_session.commit()
    return objets


def test_l_api_lit_les_usages_sans_les_montrer(client, vitrine):
    reponse = client.get("/products", params={"q": "veilleuse"}).json()
    assert [p["code"] for p in reponse] == ["TST-102"]
    assert "usages" not in reponse[0]


def test_la_categorie_s_applique_apres_la_recherche(client, vitrine):
    reponse = client.get("/products", params={"q": "renard", "category": "Décoration"}).json()
    assert [p["code"] for p in reponse] == ["TST-103"]


def test_le_tri_par_pertinence_suit_la_recherche(client, vitrine):
    reponse = client.get("/products", params={"q": "kitsune moins de 45 €", "sort": "pertinence"})
    assert [p["code"] for p in reponse.json()] == ["TST-103"]


def test_le_tri_par_pertinence_sans_requete_reste_un_tri(client, vitrine):
    reponse = client.get("/products", params={"sort": "pertinence"})
    assert reponse.status_code == 200
    assert len(reponse.json()) == 3


def test_le_back_office_ecrit_et_relit_les_usages(client, admin_headers, vitrine):
    pid = vitrine[2].id
    reponse = client.patch(f"/admin/products/{pid}", json={"usages": "Masque de fête\nÀ accrocher au mur"},
                           headers=admin_headers)
    assert reponse.status_code == 200
    assert reponse.json()["usages"] == "Masque de fête\nÀ accrocher au mur"
    trouves = client.get("/products", params={"q": "accrocher"}).json()
    assert [p["code"] for p in trouves] == ["TST-103"]


def test_des_usages_trop_longs_sont_refuses(client, admin_headers, vitrine):
    reponse = client.patch(f"/admin/products/{vitrine[0].id}", json={"usages": "x" * 1001},
                           headers=admin_headers)
    assert reponse.status_code == 422


def test_la_recherche_par_le_sens_reste_coupee_par_defaut_en_test():
    assert settings.RECHERCHE_SEMANTIQUE is False
