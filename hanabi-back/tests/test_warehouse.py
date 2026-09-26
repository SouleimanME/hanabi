"""Routes de lecture de l'entrepot decisionnel."""
import pathlib

import pytest

from app import warehouse


# --- Controle d'acces ---


def test_entrepot_refuse_les_anonymes(client):
    assert client.get("/admin/warehouse").status_code == 401


def test_entrepot_refuse_les_clients_ordinaires(client, auth_header):
    entetes, _ = auth_header(email="client@test.fr", is_admin=False)
    assert client.get("/admin/warehouse", headers=entetes).status_code == 403


def test_entrepot_ouvert_a_l_administrateur(client, auth_header):
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    assert client.get("/admin/warehouse", headers=entetes).status_code == 200


# --- Absence d'entrepot : un etat, pas une panne ---


def test_etat_annonce_l_absence_sans_echouer(client, auth_header, moteur):
    """La route repond 200 et dit pourquoi il n'y a rien a montrer."""
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    etat = client.get("/admin/warehouse", headers=entetes).json()

    assert etat["disponible"] is False
    # SQLite ne porte pas d'entrepot ; PostgreSQL le pourrait, mais rien n'est construit
    assert etat["raison"] == ("moteur" if moteur.dialect.name == "sqlite" else "non_construit")
    assert etat["construit_le"] is None
    # Sans entrepôt, aucun contrôle n'a pu tourner
    assert etat["controles"] == []
    # Les couches restent decrites
    assert [couche["cle"] for couche in etat["couches"]] == ["bronze", "silver", "gold"]
    assert all(couche["presents"] == [] for couche in etat["couches"])


def test_lecture_d_un_mart_sans_entrepot_renvoie_409(client, auth_header):
    """409 et non 404 : la table est declaree, elle n'est simplement pas construite."""
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    reponse = client.get("/admin/warehouse/marts/kpi_mensuel", headers=entetes)

    assert reponse.status_code == 409
    # Le message doit dire quoi faire, pas seulement ce qui a echoue.
    assert "dwh.py build" in reponse.json()["detail"]


def test_mart_inconnu_renvoie_404(client, auth_header):
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    reponse = client.get("/admin/warehouse/marts/inexistant", headers=entetes)
    assert reponse.status_code == 404


def test_bornes_de_pagination_refusees_avant_la_base(client, auth_header):
    """Une limite hors bornes est rejetee par la validation, pas silencieusement ramenee."""
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    assert client.get(
        f"/admin/warehouse/marts/kpi_mensuel?limite={warehouse.LIMITE_MAX + 1}",
        headers=entetes,
    ).status_code == 422
    assert client.get(
        "/admin/warehouse/marts/kpi_mensuel?decalage=-1", headers=entetes
    ).status_code == 422
    assert client.get(
        "/admin/warehouse/marts/kpi_mensuel?sens=random", headers=entetes
    ).status_code == 422


# --- Coherence du registre ---


def test_chaque_mart_est_annonce_dans_la_couche_gold():
    """Le registre et la description des couches doivent parler des memes tables."""
    gold = next(couche for couche in warehouse.COUCHES if couche["cle"] == "gold")
    for mart in warehouse.MARTS:
        assert mart.table in gold["modeles"], mart.table


def test_les_couches_decrivent_tous_les_modeles_dbt():
    """`COUCHES` doit enumerer exactement les modeles presents dans le projet dbt."""
    modeles = pathlib.Path(__file__).resolve().parents[2] / "hanabi-dwh" / "models"
    if not modeles.is_dir():
        pytest.skip("projet dbt absent de cette copie")

    for couche in warehouse.COUCHES:
        dossier = modeles / couche["cle"]
        if not dossier.is_dir():
            pytest.skip(f"couche {couche['cle']} absente du projet dbt")

        sur_disque = {fichier.stem for fichier in dossier.glob("*.sql")}
        annonces = set(couche["modeles"])

        assert sur_disque - annonces == set(), (
            f"modeles construits mais absents de COUCHES : "
            f"{sorted(sur_disque - annonces)}"
        )
        assert annonces - sur_disque == set(), (
            f"modeles annonces mais absents du projet dbt : "
            f"{sorted(annonces - sur_disque)}"
        )


def test_les_cles_de_mart_sont_uniques():
    cles = [mart.cle for mart in warehouse.MARTS]
    assert len(cles) == len(set(cles))


def test_chaque_mart_porte_une_question():
    """Une table d'agregats sans la question a laquelle elle repond est un tableau de nombres."""
    for mart in warehouse.MARTS:
        assert mart.question.endswith("?"), mart.cle


def test_format_des_colonnes_suit_le_nommage():
    """Le formatage est deduit du nom."""
    assert warehouse._format_colonne("ca_cents", "bigint") == "euro"
    assert warehouse._format_colonne("taux_marge", "numeric") == "pourcent"
    assert warehouse._format_colonne("part_ca", "numeric") == "pourcent"
    assert warehouse._format_colonne("commandes", "integer") == "entier"
    assert warehouse._format_colonne("actif", "boolean") == "booleen"
    assert warehouse._format_colonne("construit_le", "timestamp with time zone") == "date"
    assert warehouse._format_colonne("segment", "text") == "texte"
    # Un identifiant est un entier pour la base, jamais une quantite pour le
    # lecteur : « 66 164 » se lit comme un montant, « 66164 » se recopie.
    assert warehouse._format_colonne("client_id", "integer") == "identifiant"
    assert warehouse._format_colonne("id", "integer") == "identifiant"


def test_le_libelle_masque_le_suffixe_des_montants():
    assert warehouse._libelle_colonne("ca_cents") == "CA"
    assert warehouse._libelle_colonne("panier_moyen_cents") == "Panier moyen"
    assert warehouse._libelle_colonne("taux_conversion") == "Taux conversion"


def test_le_libelle_retrouve_accents_et_sigles():
    assert warehouse._libelle_colonne("jour_ferie") == "Jour férié"
    assert warehouse._libelle_colonne("segment_rfm") == "Segment RFM"
    assert warehouse._libelle_colonne("cout_cents") == "Coût"


# --- Console SQL : contrôle de forme ---
# Transaction en lecture seule, délai et examen du plan vivent dans PostgreSQL :
# ils ne se testent pas sur SQLite.


class TestFormeDesRequetes:
    def _refus(self, sql):
        with pytest.raises(warehouse.SqlRefuse) as capture:
            warehouse._valide_la_forme(sql)
        return str(capture.value)

    def test_une_lecture_simple_passe(self):
        sql = "select * from gold.gold_kpi_mensuel"
        assert warehouse._valide_la_forme(sql) == sql

    def test_une_cte_passe(self):
        """`WITH` est un debut de lecture parfaitement legitime."""
        sql = "with x as (select 1 as n) select * from x"
        assert warehouse._valide_la_forme(sql) == sql

    def test_le_point_virgule_final_est_tolere(self):
        """On le retire plutot que de refuser : le coller depuis un client SQL est le geste le plus naturel du monde."""
        assert warehouse._valide_la_forme("select 1;") == "select 1"

    @pytest.mark.parametrize(
        "sql",
        [
            "delete from gold.gold_execution",
            "update gold.gold_execution set environnement = 'x'",
            "drop table gold.gold_execution",
            "insert into gold.gold_execution values (now(), 'x', 'y', 'z')",
        ],
    )
    def test_les_ecritures_sont_refusees(self, sql):
        assert "SELECT ou WITH" in self._refus(sql)

    def test_deux_instructions_sont_refusees(self):
        """La seconde echapperait a l'examen du plan."""
        assert "seule instruction" in self._refus("select 1; drop table gold.gold_execution")

    def test_un_mot_clef_d_ecriture_cache_est_refuse(self):
        assert "TRUNCATE" in self._refus("select * from gold.gold_kpi_mensuel where 1=1 truncate")

    def test_un_mot_interdit_dans_une_chaine_ne_bloque_pas(self):
        """Regression a eviter : filtrer sur la valeur « Delete » est legitime."""
        sql = "select * from gold.gold_segments_rfm where segment = 'Delete me'"
        assert warehouse._valide_la_forme(sql) == sql

    def test_un_mot_interdit_en_commentaire_ne_bloque_pas(self):
        sql = "select 1 -- drop table gold.gold_execution"
        assert warehouse._valide_la_forme(sql) == sql

    def test_requete_vide(self):
        assert "vide" in self._refus("   ")


def test_la_console_refuse_les_anonymes(client):
    reponse = client.post("/admin/warehouse/sql", json={"sql": "select 1"})
    assert reponse.status_code == 401


def test_la_console_refuse_les_clients_ordinaires(client, auth_header):
    entetes, _ = auth_header(email="client@test.fr", is_admin=False)
    reponse = client.post("/admin/warehouse/sql", json={"sql": "select 1"}, headers=entetes)
    assert reponse.status_code == 403


def test_la_console_sans_entrepot_renvoie_409(client, auth_header, moteur):
    """Sur SQLite l'entrepot n'existe pas : la console le dit, sans exploser."""
    if moteur.dialect.name != "sqlite":
        pytest.skip("sur PostgreSQL, `select 1` ne lit aucune table et passe sans entrepot")
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    reponse = client.post(
        "/admin/warehouse/sql", json={"sql": "select 1"}, headers=entetes
    )
    assert reponse.status_code == 409
    assert "dwh.py build" in reponse.json()["detail"]


def test_les_schemas_ouverts_excluent_public():
    """`public` porte les condensats de mots de passe."""
    assert "public" not in warehouse.SCHEMAS_AUTORISES
    assert warehouse.SCHEMAS_AUTORISES == frozenset(
        {"bronze", "silver", "gold", "externe", "controles"}
    )
