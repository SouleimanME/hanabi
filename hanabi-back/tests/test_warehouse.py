"""Routes de lecture de l'entrepot decisionnel.

La suite tourne sur SQLite, ou l'entrepot n'existe pas et ne peut pas exister :
ses modeles emploient `date_trunc`, `generate_series` et des fonctions de
fenetrage. Ces tests verifient donc surtout ce qui doit rester vrai quel que
soit le moteur - le controle d'acces, la coherence du registre, et le fait que
l'absence d'entrepot se traduise par un etat annonce et non par une erreur 500.

Le contenu des agregats, lui, est verifie par les tests dbt (`dbt build` joue
133 assertions sur la base PostgreSQL), pas ici : le rejouer en Python
reviendrait a reecrire les modeles une seconde fois, et donc a tester la copie
plutot que l'original.
"""
import pytest

from app import warehouse


# --------------------------------------------------------------------------
# Controle d'acces
# --------------------------------------------------------------------------


def test_entrepot_refuse_les_anonymes(client):
    assert client.get("/admin/warehouse").status_code == 401


def test_entrepot_refuse_les_clients_ordinaires(client, auth_header):
    entetes, _ = auth_header(email="client@test.fr", is_admin=False)
    assert client.get("/admin/warehouse", headers=entetes).status_code == 403


def test_entrepot_ouvert_a_l_administrateur(client, auth_header):
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    assert client.get("/admin/warehouse", headers=entetes).status_code == 200


# --------------------------------------------------------------------------
# Absence d'entrepot : un etat, pas une panne
# --------------------------------------------------------------------------


def test_etat_annonce_l_absence_sans_echouer(client, auth_header):
    """Sur SQLite, la route repond 200 et dit pourquoi il n'y a rien a montrer.

    Un 503 obligerait l'interface a traiter un cas d'erreur pour ce qui est la
    situation normale en developpement.
    """
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    etat = client.get("/admin/warehouse", headers=entetes).json()

    assert etat["disponible"] is False
    assert etat["raison"] == "moteur"
    assert etat["construit_le"] is None
    # Les couches restent decrites : l'interface dessine le graphe attendu et
    # signale que rien n'en est present, ce qui est plus parlant qu'une page
    # vide.
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


# --------------------------------------------------------------------------
# Coherence du registre
# --------------------------------------------------------------------------


def test_chaque_mart_est_annonce_dans_la_couche_gold():
    """Le registre et la description des couches doivent parler des memes tables.

    Les deux sont ecrits a la main dans `warehouse.py`, l'un pour interroger,
    l'autre pour dessiner le graphe. Rien n'empeche d'ajouter une table au
    premier en oubliant le second - sinon ce test.
    """
    gold = next(couche for couche in warehouse.COUCHES if couche["cle"] == "gold")
    for mart in warehouse.MARTS:
        assert mart.table in gold["modeles"], mart.table


def test_les_cles_de_mart_sont_uniques():
    cles = [mart.cle for mart in warehouse.MARTS]
    assert len(cles) == len(set(cles))


def test_chaque_mart_porte_une_question():
    """Une table d'agregats sans la question a laquelle elle repond est un
    tableau de nombres, et l'interface s'appuie sur ce texte."""
    for mart in warehouse.MARTS:
        assert mart.question.endswith("?"), mart.cle


def test_format_des_colonnes_suit_le_nommage():
    """Le formatage est deduit du nom, faute de quoi il faudrait decrire a la
    main une centaine de colonnes - une liste que personne ne tiendrait."""
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
    """« Ca cents » au-dessus d'une colonne affichee en euros serait une
    contradiction sous les yeux du lecteur."""
    assert warehouse._libelle_colonne("ca_cents") == "Ca"
    assert warehouse._libelle_colonne("panier_moyen_cents") == "Panier moyen"
    assert warehouse._libelle_colonne("taux_conversion") == "Taux conversion"


# --------------------------------------------------------------------------
# Console SQL : les barrieres de forme
# --------------------------------------------------------------------------
#
# Les trois barrieres qui comptent vraiment - transaction en lecture seule,
# delai d'execution, examen du plan par PostgreSQL - ne peuvent pas etre
# testees ici : elles vivent dans la base, et la suite tourne sur SQLite. Ce
# sont celles qu'on verifie a la main sur PostgreSQL, et elles sont decrites
# dans le module.
#
# Ce qui suit teste la premiere barriere, celle qui s'applique au texte de la
# requete avant toute connexion. Elle n'est pas la plus solide, mais c'est elle
# qui rend les messages comprehensibles, et c'est elle qu'un refactoring casse
# sans s'en apercevoir.


class TestFormeDesRequetes:
    def _refus(self, sql):
        with pytest.raises(warehouse.SqlRefuse) as capture:
            warehouse._valide_la_forme(sql)
        return str(capture.value)

    def test_une_lecture_simple_passe(self):
        sql = "select * from gold.gold_kpi_mensuel"
        assert warehouse._valide_la_forme(sql) == sql

    def test_une_cte_passe(self):
        """`WITH` est un debut de lecture parfaitement legitime, et c'est la
        forme qu'on ecrit des que la requete se complique."""
        sql = "with x as (select 1 as n) select * from x"
        assert warehouse._valide_la_forme(sql) == sql

    def test_le_point_virgule_final_est_tolere(self):
        """On le retire plutot que de refuser : le coller depuis un client SQL
        est le geste le plus naturel du monde."""
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
        """La seconde echapperait a l'examen du plan, qui ne porte que sur la
        premiere - c'est exactement le chemin d'une injection."""
        assert "seule instruction" in self._refus("select 1; drop table gold.gold_execution")

    def test_un_mot_clef_d_ecriture_cache_est_refuse(self):
        assert "TRUNCATE" in self._refus("select * from gold.gold_kpi_mensuel where 1=1 truncate")

    def test_un_mot_interdit_dans_une_chaine_ne_bloque_pas(self):
        """Regression a eviter : filtrer sur la valeur « Delete » est legitime.

        Chercher les mots-clefs dans le texte brut refuserait cette requete, et
        l'utilisateur n'aurait aucun moyen de comprendre pourquoi.
        """
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


def test_la_console_sans_entrepot_renvoie_409(client, auth_header):
    """Sur SQLite l'entrepot n'existe pas : la console le dit, sans exploser."""
    entetes, _ = auth_header(email="chef@test.fr", is_admin=True)
    reponse = client.post(
        "/admin/warehouse/sql", json={"sql": "select 1"}, headers=entetes
    )
    assert reponse.status_code == 409
    assert "dwh.py build" in reponse.json()["detail"]


def test_les_schemas_ouverts_excluent_public():
    """`public` porte les condensats de mots de passe. Il ne doit jamais entrer
    dans la liste des schemas lisibles, quelle qu'en soit la raison.

    La liste est epinglee en entier, et pas seulement l'absence de `public` :
    l'elargir doit demander de modifier ce test, donc de justifier l'ajout au
    lieu de le glisser.

    `externe` en fait partie depuis qu'il accueille les sources publiques
    chargees par l'entrepot, taux de change de la BCE et jours feries. Ces
    tables ne contiennent aucune donnee personnelle : elles viennent d'API
    ouvertes et sont deja publiques a la source.
    """
    assert "public" not in warehouse.SCHEMAS_AUTORISES
    assert warehouse.SCHEMAS_AUTORISES == frozenset(
        {"bronze", "silver", "gold", "externe"}
    )
