"""Demander à l'entrepôt : la question devient du SQL, la console l'exécute.

Sur SQLite, l'entrepôt n'existe pas : le schéma et la console sont simulés
pour vérifier le déroulé. Sur PostgreSQL (TEST_DATABASE_URL), un petit schéma
gold réel vérifie la lecture des colonnes et les garde-fous de la console.
"""
import json

import pytest
from sqlalchemy import text

from app import models, question_entrepot, warehouse
from app.config import settings
from app.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, ensure_public_admin

SCHEMA = "gold.gold_segments_rfm : Segments RFM.\n  - segment (text) valeurs : 'A risque', 'Champions'"
SQL = "select clients from gold.gold_segments_rfm where segment = 'Champions'"


class Fournisseur:
    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.recus = []

    def __call__(self, corps):
        self.recus.append(corps)
        reponse = self.reponses.pop(0)
        contenu = reponse if isinstance(reponse, str) else json.dumps(reponse, ensure_ascii=False)
        return {"choices": [{"message": {"content": contenu}}]}


class Console:
    """`executer_sql` simulé : refuse ce qu'on lui dit de refuser, note le reste."""

    def __init__(self, *refus):
        self.refus = list(refus)
        self.appels = []

    def __call__(self, db, sql, limite, schemas):
        self.appels.append({"sql": sql, "limite": limite, "schemas": schemas})
        if self.refus:
            raise warehouse.SqlRefuse(self.refus.pop(0))
        return {"sql": sql, "colonnes": [{"nom": "clients"}], "lignes": [[412]], "total": 1}


def _traduction(sql=SQL, explication="Nombre de clients du segment Champions."):
    return {"sql": sql, "explication": explication, "refus": None}


@pytest.fixture(autouse=True)
def configure(monkeypatch):
    monkeypatch.setattr(settings, "REDACTION_URL", "https://fournisseur.example/v1")
    monkeypatch.setattr(settings, "REDACTION_CLE", "cle-de-test")
    monkeypatch.setattr(settings, "REDACTION_MODELE", "modele-de-test")


@pytest.fixture
def entrepot(monkeypatch):
    """Schéma et console simulés ; rend un réglage (fournisseur, console)."""

    def poser(reponses, refus=()):
        faux = Fournisseur(*reponses)
        console = Console(*refus)
        monkeypatch.setattr("app.fournisseur.transport", faux)
        monkeypatch.setattr(question_entrepot, "contexte", lambda db: SCHEMA)
        monkeypatch.setattr(warehouse, "executer_sql", console)
        return faux, console

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


def _demander(client, headers, question="Combien de clients sont des Champions ?"):
    return client.post("/admin/warehouse/question", json={"question": question}, headers=headers)


# --- Déroulé ---


def test_la_question_devient_une_requete_executee_par_la_console(client, admin, entrepot):
    faux, console = entrepot([_traduction()])
    corps = _demander(client, admin).json()
    assert corps["sql"] == SQL
    assert corps["explication"] == "Nombre de clients du segment Champions."
    assert corps["resultat"]["lignes"] == [[412]]
    assert corps["tentatives"] == 1
    # Le modèle voit le schéma et la question
    assert SCHEMA in faux.recus[0]["messages"][1]["content"]
    assert faux.recus[0]["messages"][1]["content"].endswith("Combien de clients sont des Champions ?")


def test_la_console_ne_lit_que_gold_meme_pour_un_administrateur(client, admin, entrepot):
    _, console = entrepot([_traduction()])
    _demander(client, admin)
    assert console.appels[0]["schemas"] == frozenset({"gold"})
    assert console.appels[0]["limite"] == question_entrepot.LIMITE


def test_une_requete_refusee_par_la_base_est_corrigee_une_fois(client, admin, entrepot):
    faux, console = entrepot(
        [_traduction(sql="select client from gold.gold_segments_rfm"), _traduction()],
        refus=['column "client" does not exist'],
    )
    corps = _demander(client, admin).json()
    assert corps["tentatives"] == 2
    assert corps["sql"] == SQL
    assert 'column "client" does not exist' in faux.recus[1]["messages"][-1]["content"]


def test_deux_refus_de_la_base_montrent_le_sql_et_pourquoi(client, admin, entrepot, db_session):
    entrepot([_traduction(), _traduction()], refus=["Lecture refusée sur public.users.", "Toujours refusée."])
    reponse = _demander(client, admin)
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["resultat"] is None
    assert corps["erreur"] == "Toujours refusée."
    assert corps["sql"] == SQL
    assert db_session.query(models.QuestionEntrepot).one().statut == "echec"


def test_un_refus_du_modele_n_execute_rien(client, admin, entrepot, db_session):
    _, console = entrepot([{"sql": None, "explication": None,
                            "refus": "Les adresses e-mail ne sont pas dans l'entrepôt."}])
    corps = _demander(client, admin, "Les e-mails des clients Champions").json()
    assert corps["refus"] == "Les adresses e-mail ne sont pas dans l'entrepôt."
    assert corps["resultat"] is None
    assert console.appels == []
    assert db_session.query(models.QuestionEntrepot).one().statut == "refus"


def test_une_reponse_illisible_deux_fois_est_une_erreur_franche(client, admin, entrepot):
    entrepot(["pas du json", {"sql": None, "refus": None}])
    reponse = _demander(client, admin)
    assert reponse.status_code == 502


# --- Garde-fous ---


def test_sans_entrepot_rien_ne_part_chez_le_fournisseur(client, admin, monkeypatch, db_session):
    faux = Fournisseur()
    monkeypatch.setattr("app.fournisseur.transport", faux)
    reponse = _demander(client, admin)
    assert reponse.status_code == 409
    assert faux.recus == []
    assert db_session.query(models.QuestionEntrepot).count() == 0


def test_non_configure_le_champ_n_apparait_pas(client, admin, monkeypatch):
    monkeypatch.setattr(settings, "REDACTION_URL", "")
    assert client.get("/admin/warehouse/sql/aide", headers=admin).json()["questions"] is False
    assert _demander(client, admin).status_code == 503


def test_la_demonstration_pose_des_questions_avec_son_propre_plafond(client, admin, demo, entrepot, monkeypatch):
    monkeypatch.setattr(settings, "QUESTIONS_PLAFOND_DEMO", 1)
    entrepot([_traduction(), _traduction(), _traduction()])
    assert _demander(client, demo).status_code == 200
    reponse = _demander(client, demo)
    assert reponse.status_code == 429
    assert "demain" in reponse.json()["detail"]
    assert _demander(client, admin).status_code == 200


def test_un_client_n_a_pas_acces(client, auth_header, entrepot):
    headers, _ = auth_header(email="client@test.fr")
    entrepot([_traduction()])
    assert _demander(client, headers).status_code == 403


def test_une_question_trop_longue_est_refusee(client, admin, entrepot):
    entrepot([_traduction()])
    assert _demander(client, admin, "x" * 301).status_code == 422


def test_le_journal_ne_garde_ni_question_ni_sql():
    colonnes = {c.name for c in models.QuestionEntrepot.__table__.columns}
    assert colonnes == {"id", "created_at", "demo", "statut", "tentatives", "duree_ms"}


# --- Sur un vrai PostgreSQL ---


@pytest.fixture
def gold(moteur):
    if moteur.dialect.name != "postgresql":
        pytest.skip("demande PostgreSQL (TEST_DATABASE_URL)")
    question_entrepot._contexte.clear()
    with moteur.begin() as cx:
        cx.execute(text("drop schema if exists gold cascade"))
        cx.execute(text("create schema gold"))
        cx.execute(text("create table gold.gold_segments_rfm (segment text, rang int, clients int, ca_cents bigint)"))
        cx.execute(text("insert into gold.gold_segments_rfm values "
                        "('Champions', 1, 412, 9000000), ('A risque', 5, 800, 2000000)"))
        cx.execute(text("create table gold.gold_execution (construit_le timestamptz)"))
        cx.execute(text("insert into gold.gold_execution values (now())"))
    yield moteur
    question_entrepot._contexte.clear()
    with moteur.begin() as cx:
        cx.execute(text("drop schema gold cascade"))


def test_le_schema_se_lit_dans_la_base_avec_ses_valeurs(gold, db_session):
    schema = question_entrepot.contexte(db_session)
    assert "gold.gold_segments_rfm : Segments RFM." in schema
    assert "segment (text) valeurs : 'A risque', 'Champions'" in schema
    assert "clients (integer)" in schema
    # Une table absente de l'entrepôt n'est pas décrite
    assert "gold_kpi_mensuel" not in schema


def test_la_console_refuse_une_table_hors_de_gold(gold, client, admin, monkeypatch, db_session):
    faux = Fournisseur(_traduction(sql="select count(*) from public.users"),
                       _traduction(sql="select email from public.users"))
    monkeypatch.setattr("app.fournisseur.transport", faux)
    corps = _demander(client, admin).json()
    assert corps["resultat"] is None
    assert "public.users" in corps["erreur"]


def test_une_vraie_requete_rend_le_resultat(gold, client, admin, monkeypatch):
    monkeypatch.setattr("app.fournisseur.transport", Fournisseur(_traduction()))
    corps = _demander(client, admin).json()
    assert corps["resultat"]["lignes"] == [[412]]

# --- Comparaison des résultats, pour l'évaluation ---


def _res(colonnes, lignes):
    return {"colonnes": [{"nom": c} for c in colonnes], "lignes": lignes}


def test_les_noms_et_colonnes_en_plus_ne_comptent_pas():
    from entrepot.comparer import meme_reponse

    reference = _res(["mois"], [["2026-08"]])
    assert meme_reponse(reference, _res(["mois_record", "ca_cents"], [["2026-08", 912000]]))


def test_une_valeur_differente_ou_une_ligne_de_trop_est_fausse():
    from entrepot.comparer import meme_reponse

    reference = _res(["produit"], [["Lampe Lune"], ["Daruma Rouge"]])
    assert not meme_reponse(reference, _res(["produit"], [["Lampe Lune"], ["Kokeshi Hana"]]))
    assert not meme_reponse(reference, _res(["produit"], [["Lampe Lune"], ["Daruma Rouge"], ["Kokeshi Hana"]]))


def test_l_ordre_ne_compte_que_s_il_est_demande():
    from entrepot.comparer import meme_reponse

    reference = _res(["produit"], [["Lampe Lune"], ["Daruma Rouge"]])
    inverse = _res(["produit"], [["Daruma Rouge"], ["Lampe Lune"]])
    assert meme_reponse(reference, inverse)
    assert not meme_reponse(reference, inverse, ordonne=True)


def test_les_nombres_se_comparent_a_deux_decimales():
    from decimal import Decimal

    from entrepot.comparer import meme_reponse

    assert meme_reponse(_res(["part_ca"], [[Decimal("0.2314")]]), _res(["part"], [[0.23138]]))
