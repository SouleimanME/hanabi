"""Assistant de fiche produit, face à un faux fournisseur : forme de la
réponse, second essai, photo refusée, plafonds, accès."""
import io
import json
import urllib.error

import pytest

from app import models, redaction
from app.config import settings
from app.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, ensure_public_admin

PHOTO = "https://images.example/kitsune.jpg"


def _fiche(nom, usages=("Ligne une", "Ligne deux", "Ligne trois"), alt="Renard blanc assis"):
    return {"name": nom, "blurb": "Résine peinte main, 18 cm", "usages": list(usages), "alt": alt}


VALIDE = {
    "categorie": "Figurines",
    "fr": _fiche("Figurine Kitsune"),
    "en": _fiche("Kitsune Figure"),
    "es": _fiche("Figura Kitsune"),
}


class Fournisseur:
    """Rend les réponses prévues, dans l'ordre, et garde les corps reçus."""

    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.recus = []

    def __call__(self, corps):
        self.recus.append(corps)
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        contenu = reponse if isinstance(reponse, str) else json.dumps(reponse, ensure_ascii=False)
        return {"choices": [{"message": {"content": contenu}}]}


def _http(code):
    return urllib.error.HTTPError("https://x", code, "refus", {}, io.BytesIO(b""))


@pytest.fixture(autouse=True)
def configure(monkeypatch):
    monkeypatch.setattr(settings, "REDACTION_URL", "https://fournisseur.example/v1")
    monkeypatch.setattr(settings, "REDACTION_CLE", "cle-de-test")
    monkeypatch.setattr(settings, "REDACTION_MODELE", "modele-de-test")


@pytest.fixture
def fournisseur(monkeypatch):
    def poser(*reponses):
        faux = Fournisseur(*reponses)
        monkeypatch.setattr(redaction, "transport", faux)
        return faux

    return poser


@pytest.fixture
def admin(auth_header):
    headers, _ = auth_header(email="admin@test.fr", is_admin=True)
    return headers


@pytest.fixture
def demo(client, db_session, antibot_for):
    ensure_public_admin(db_session)
    res = client.post("/auth/login", json={
        "email": DEMO_ADMIN_EMAIL, "password": DEMO_ADMIN_PASSWORD, "antibot": antibot_for("login"),
    })
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _demander(client, headers, **champs):
    corps = {"name": "Kitsune", "notes": "renard blanc, résine", "image": PHOTO, **champs}
    return client.post("/admin/redaction/fiche", json=corps, headers=headers)


# --- Réponse ---


def test_une_proposition_valide_remplit_les_trois_langues(client, admin, fournisseur):
    faux = fournisseur(VALIDE)
    reponse = _demander(client, admin)
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["categorie"] == "Figurines"
    assert corps["en"]["name"] == "Kitsune Figure"
    assert corps["fr"]["usages"] == "Ligne une\nLigne deux\nLigne trois"
    assert corps["photo_lue"] is True
    # Le fournisseur a reçu la photo, le modèle choisi et la demande de JSON
    envoye = faux.recus[0]
    assert envoye["model"] == "modele-de-test"
    assert envoye["response_format"] == {"type": "json_object"}
    assert {"type": "image_url", "image_url": {"url": PHOTO}} in envoye["messages"][1]["content"]


def test_les_notes_du_marchand_partent_avec_la_demande(client, admin, fournisseur):
    faux = fournisseur(VALIDE)
    _demander(client, admin, notes="socle en bois de cerisier")
    texte = faux.recus[0]["messages"][1]["content"][0]["text"]
    assert "socle en bois de cerisier" in texte


def test_le_catalogue_donne_le_ton(client, admin, fournisseur, db_session):
    from app.seed import seed

    seed(db_session)
    faux = fournisseur(VALIDE)
    _demander(client, admin)
    consigne = faux.recus[0]["messages"][0]["content"]
    assert "Fiches existantes" in consigne
    assert "Kitsune Figure" in consigne


def test_une_reponse_entouree_de_texte_est_lue(client, admin, fournisseur):
    fournisseur("Voici la fiche :\n```json\n" + json.dumps(VALIDE) + "\n```")
    assert _demander(client, admin).status_code == 200


def test_les_tirets_cadratins_sont_remplaces(client, admin, fournisseur):
    fiche = dict(VALIDE, fr=_fiche("Figurine Kitsune") | {"blurb": "Résine — peinte main"})
    fournisseur(fiche)
    assert _demander(client, admin).json()["fr"]["blurb"] == "Résine, peinte main"


def test_une_reponse_invalide_est_redemandee_une_fois(client, admin, fournisseur):
    faux = fournisseur(dict(VALIDE, categorie="Vaisselle"), VALIDE)
    reponse = _demander(client, admin)
    assert reponse.status_code == 200
    assert len(faux.recus) == 2
    # Le second essai dit ce qui n'allait pas
    assert "categorie" in faux.recus[1]["messages"][-1]["content"]


def test_deux_reponses_invalides_ne_remplissent_rien(client, admin, fournisseur):
    fournisseur("pas du json", "toujours pas")
    reponse = _demander(client, admin)
    assert reponse.status_code == 502
    assert "forme attendue" in reponse.json()["detail"]


def test_des_langues_desalignees_sont_refusees(client, admin, fournisseur):
    boiteuse = dict(VALIDE, es=_fiche("Figura Kitsune", usages=("Una sola línea",)))
    faux = fournisseur(boiteuse, VALIDE)
    assert _demander(client, admin).status_code == 200
    assert len(faux.recus) == 2


# --- Photo ---


def test_une_photo_refusee_par_le_fournisseur_est_abandonnee(client, admin, fournisseur):
    faux = fournisseur(_http(400), VALIDE)
    corps = _demander(client, admin).json()
    assert corps["photo_lue"] is False
    # Sans photo vue, pas de texte alternatif inventé
    assert corps["fr"]["alt"] == corps["en"]["alt"] == ""
    assert all(c["type"] == "text" for c in faux.recus[1]["messages"][1]["content"])


@pytest.mark.parametrize("image", ["http://images.example/a.jpg", "file:///etc/passwd",
                                   "javascript:alert(1)", "data:text/html;base64,PGI+"])
def test_seules_les_photos_https_ou_integrees_sont_acceptees(client, admin, fournisseur, image):
    fournisseur(VALIDE)
    assert _demander(client, admin, image=image).status_code == 422


def test_sans_photo_la_demande_le_dit(client, admin, fournisseur):
    faux = fournisseur(VALIDE)
    corps = _demander(client, admin, image=None).json()
    assert "aucune" in faux.recus[0]["messages"][1]["content"][0]["text"]
    assert corps["fr"]["alt"] == ""


# --- Fournisseur en panne ---


@pytest.mark.parametrize("erreur, statut, mot", [
    (_http(401), 503, "clé"),
    (_http(429), 503, "saturé"),
    (_http(500), 502, "500"),
    (urllib.error.URLError("hors ligne"), 504, "ne répond pas"),
])
def test_une_panne_du_fournisseur_s_explique(client, admin, fournisseur, erreur, statut, mot):
    fournisseur(erreur)
    reponse = _demander(client, admin)
    assert reponse.status_code == statut
    assert mot in reponse.json()["detail"]


def test_non_configure_l_assistant_est_absent(client, admin, monkeypatch):
    monkeypatch.setattr(settings, "REDACTION_URL", "")
    assert client.get("/admin/redaction/etat", headers=admin).json()["actif"] is False
    assert _demander(client, admin).status_code == 503


# --- Plafonds et accès ---


def test_chaque_demande_compte_meme_un_echec(client, admin, fournisseur, db_session):
    fournisseur(VALIDE, _http(500))
    _demander(client, admin)
    _demander(client, admin)
    statuts = sorted(r.statut for r in db_session.query(models.Redaction))
    assert statuts == ["echec", "ok"]
    etat = client.get("/admin/redaction/etat", headers=admin).json()
    assert etat["restant"] == settings.REDACTION_PLAFOND_JOUR - 2


def test_le_plafond_du_jour_arrete_l_assistant(client, admin, fournisseur, monkeypatch):
    monkeypatch.setattr(settings, "REDACTION_PLAFOND_JOUR", 1)
    fournisseur(VALIDE, VALIDE)
    assert _demander(client, admin).status_code == 200
    reponse = _demander(client, admin)
    assert reponse.status_code == 429
    assert "demain" in reponse.json()["detail"]


def test_la_demonstration_a_son_propre_plafond(client, admin, demo, fournisseur, monkeypatch):
    monkeypatch.setattr(settings, "REDACTION_PLAFOND_DEMO", 1)
    fournisseur(VALIDE, VALIDE, VALIDE)
    assert _demander(client, demo).status_code == 200
    assert _demander(client, demo).status_code == 429
    # Le visiteur n'a pas entamé le quota du marchand
    assert _demander(client, admin).status_code == 200


def test_la_demonstration_propose_sans_pouvoir_enregistrer(client, demo, fournisseur, db_session):
    from app.seed import seed

    seed(db_session)
    fournisseur(VALIDE)
    assert _demander(client, demo).status_code == 200
    pid = db_session.query(models.Product).first().id
    assert client.patch(f"/admin/products/{pid}", json={"name": "Autre"}, headers=demo).status_code == 403


def test_un_client_n_a_pas_acces(client, auth_header, fournisseur):
    headers, _ = auth_header(email="client@test.fr")
    fournisseur(VALIDE)
    assert _demander(client, headers).status_code == 403


def test_le_journal_ne_garde_personne(db_session):
    colonnes = {c.name for c in models.Redaction.__table__.columns}
    assert colonnes == {"id", "created_at", "demo", "statut", "photo_lue", "duree_ms"}
