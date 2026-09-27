"""Ce que les visiteurs cherchent sans le trouver : ce qui est noté, ce qui ne
l'est jamais, et le regroupement en besoins."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app import demandes, models
from app.config import settings
from app.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, ensure_public_admin, seed


class Fournisseur:
    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.recus = []

    def __call__(self, corps):
        self.recus.append(corps)
        reponse = self.reponses.pop(0)
        contenu = reponse if isinstance(reponse, str) else json.dumps(reponse, ensure_ascii=False)
        return {"choices": [{"message": {"content": contenu}}]}


@pytest.fixture(autouse=True)
def boutique(monkeypatch, db_session):
    monkeypatch.setattr(settings, "REDACTION_URL", "https://fournisseur.example/v1")
    monkeypatch.setattr(settings, "REDACTION_CLE", "cle-de-test")
    monkeypatch.setattr(settings, "REDACTION_MODELE", "modele-de-test")
    demandes._cache.clear()
    demandes._derniere_purge[0] = None
    seed(db_session)


@pytest.fixture
def fournisseur(monkeypatch):
    def poser(*reponses):
        faux = Fournisseur(*reponses)
        monkeypatch.setattr("app.fournisseur.transport", faux)
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
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _notes(db):
    return [(d.source, d.texte) for d in db.query(models.DemandeSansReponse).order_by(models.DemandeSansReponse.id)]


def _conseil(client, antibot_for, demande):
    return client.post("/conseil", json={"demande": demande, "lang": "fr", "antibot": antibot_for("conseil")})


# --- Recherche ---


def test_une_recherche_sans_resultat_est_notee(client, db_session):
    assert client.get("/products", params={"q": "Coque   iPhone"}).json() == []
    assert _notes(db_session) == [("recherche", "coque iphone")]


def test_une_recherche_qui_trouve_n_est_pas_notee(client, db_session):
    assert client.get("/products", params={"q": "kitsune"}).json()
    assert _notes(db_session) == []


def test_un_filtre_de_famille_vide_ne_dit_rien_du_catalogue(client, db_session):
    # La lampe existe, mais pas parmi les figurines
    client.get("/products", params={"q": "lampe", "category": "Figurines"})
    assert _notes(db_session) == []


def test_trois_lettres_au_moins(client, db_session):
    client.get("/products", params={"q": "zq"})
    assert _notes(db_session) == []


def test_un_plafond_par_jour(client, db_session, monkeypatch):
    monkeypatch.setattr(demandes, "PLAFOND_JOUR", 2)
    for q in ("coque", "étui", "sac"):
        client.get("/products", params={"q": q})
    assert len(_notes(db_session)) == 2


# --- Conseiller ---


def test_le_conseiller_ne_garde_que_le_besoin_jamais_la_demande(
    client, antibot_for, fournisseur, db_session
):
    fournisseur({"message": "Rien ici ne protège un téléphone.", "choix": [], "besoin": "coque de téléphone"})
    _conseil(client, antibot_for, "Pour protéger le téléphone de Marie qui habite à Lyon")
    assert _notes(db_session) == [("conseil", "coque de téléphone")]
    textes = " ".join(t for _, t in _notes(db_session))
    assert "Marie" not in textes and "Lyon" not in textes


def test_une_reponse_avec_des_objets_ne_note_rien(client, antibot_for, fournisseur, db_session):
    fournisseur({
        "message": "Une piste.", "besoin": "figurine",
        "choix": [{"code": "HNB-052", "raison": "Un esprit renard du folklore japonais."}],
    })
    _conseil(client, antibot_for, "Pour ma sœur qui aime les yokai")
    assert _notes(db_session) == []


def test_un_budget_que_rien_ne_tient(client, antibot_for, fournisseur, db_session):
    faux = fournisseur()
    _conseil(client, antibot_for, "Un cadeau à moins de 5 €")
    assert faux.recus == []
    assert _notes(db_session) == [("conseil", "cadeau à moins de 5 €")]


def test_un_besoin_trop_long_est_coupe_sans_redemander(client, antibot_for, fournisseur, db_session):
    faux = fournisseur({"message": "Rien.", "choix": [], "besoin": "x" * 200})
    assert _conseil(client, antibot_for, "Quelque chose d'introuvable").status_code == 200
    assert len(faux.recus) == 1
    assert len(_notes(db_session)[0][1]) == 80


# --- Synthèse ---


def _semer(db, *lignes):
    for source, texte, fois in lignes:
        for _ in range(fois):
            db.add(models.DemandeSansReponse(source=source, texte=texte, lang="fr"))
    db.commit()


def test_le_modele_regroupe_et_le_serveur_compte(client, admin, fournisseur, db_session):
    _semer(db_session, ("recherche", "coque iphone", 3), ("recherche", "phone case", 1),
           ("conseil", "coque de téléphone", 2), ("recherche", "tapis de souris", 1))
    faux = fournisseur({"groupes": [
        # Le modèle se trompe de compte et répète une ligne : ni l'un ni l'autre ne passe
        {"besoin": "Coque de téléphone", "lignes": [1, 2, 3], "demandes": 999},
        {"besoin": "Doublon", "lignes": [1]},
        {"besoin": "Hors liste", "lignes": [42]},
    ]})

    corps = client.get("/admin/demandes", headers=admin).json()

    assert corps["regroupe"] is True and corps["total"] == 7
    coque, tapis = corps["besoins"]
    assert coque["besoin"] == "Coque de téléphone"
    assert coque["demandes"] == 6
    assert coque["sources"] == {"recherche": 4, "conseil": 2}
    assert coque["exemples"][0] == "coque iphone"
    # Oubliée par le modèle, la ligne reste visible, seule
    assert (tapis["besoin"], tapis["demandes"]) == ("tapis de souris", 1)
    assert "coque iphone" in faux.recus[0]["messages"][1]["content"]


def test_rouvrir_l_ecran_ne_rappelle_pas_le_modele(client, admin, fournisseur, db_session):
    _semer(db_session, ("recherche", "coque iphone", 1))
    faux = fournisseur({"groupes": [{"besoin": "Coque", "lignes": [1]}]})
    client.get("/admin/demandes", headers=admin)
    client.get("/admin/demandes", headers=admin)
    assert len(faux.recus) == 1


def test_sans_fournisseur_chaque_texte_est_son_groupe(client, admin, db_session, monkeypatch):
    monkeypatch.setattr(settings, "REDACTION_URL", "")
    _semer(db_session, ("recherche", "coque iphone", 2), ("conseil", "coque iphone", 1))
    corps = client.get("/admin/demandes", headers=admin).json()
    assert corps["regroupe"] is False
    assert corps["besoins"][0]["demandes"] == 3


def test_une_reponse_illisible_laisse_la_liste_brute(client, admin, fournisseur, db_session):
    _semer(db_session, ("recherche", "coque iphone", 1))
    fournisseur("pas du JSON")
    corps = client.get("/admin/demandes", headers=admin).json()
    assert corps["regroupe"] is False
    assert corps["besoins"][0]["besoin"] == "coque iphone"


def test_la_demonstration_ne_voit_pas_ce_que_les_visiteurs_ont_tape(client, demo, fournisseur, db_session):
    _semer(db_session, ("recherche", "cadeau pour jean dupont", 1))
    fournisseur({"groupes": [{"besoin": "Cadeau personnalisé", "lignes": [1]}]})
    corps = client.get("/admin/demandes", headers=demo).json()
    assert corps["besoins"][0]["besoin"] == "Cadeau personnalisé"
    assert corps["besoins"][0]["exemples"] == []
    assert "dupont" not in json.dumps(corps)


def test_reserve_au_back_office(client, auth_header):
    headers, _ = auth_header()
    assert client.get("/admin/demandes", headers=headers).status_code == 403


def test_trente_jours_puis_effacees(db_session):
    vieille = models.DemandeSansReponse(source="recherche", texte="ancienne", lang="fr")
    vieille.created_at = datetime.now(timezone.utc) - timedelta(days=31)
    db_session.add(vieille)
    _semer(db_session, ("recherche", "recente", 1))
    assert demandes.purger(db_session) == 1
    assert [t for _, t in _notes(db_session)] == ["recente"]
