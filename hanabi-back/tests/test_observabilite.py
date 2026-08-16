"""Identifiant de requete et journal structure.

Ce que ces tests protegent : la capacite a repondre, apres coup, a la question
« qu'est-il arrive a CETTE requete-la ». Sans identifiant partage entre la
reponse et les journaux, un signalement d'utilisateur n'est rattachable a rien.
"""
import json
import logging

from app.observability import EN_TETE, FormatJSON, _reseau, id_requete


class TestIdentifiantDeRequete:
    def test_chaque_reponse_en_porte_un(self, client):
        res = client.get("/")

        assert EN_TETE in res.headers
        assert len(res.headers[EN_TETE]) >= 8

    def test_deux_requetes_ont_des_identifiants_differents(self, client):
        premier = client.get("/").headers[EN_TETE]
        second = client.get("/").headers[EN_TETE]

        assert premier != second

    def test_l_identifiant_du_client_est_repris(self, client):
        """Permet de suivre un appel a travers plusieurs services.

        Quand la boutique, l'API et un traitement de fond partagent la meme
        reference, une trace se lit de bout en bout au lieu de s'arreter a
        chaque frontiere.
        """
        res = client.get("/", headers={EN_TETE: "trace-du-client-42"})

        assert res.headers[EN_TETE] == "trace-du-client-42"

    def test_un_identifiant_demesure_est_tronque(self, client):
        """Il traverse les journaux : rien n'empeche d'y glisser un roman."""
        res = client.get("/", headers={EN_TETE: "x" * 5000})

        assert len(res.headers[EN_TETE]) <= 64

    def test_un_identifiant_vide_est_remplace(self, client):
        res = client.get("/", headers={EN_TETE: "   "})

        assert res.headers[EN_TETE].strip()

    def test_la_duree_de_traitement_est_exposee(self, client):
        """`Server-Timing` distingue une lenteur serveur d'une lenteur reseau,
        sans qu'il faille acceder aux journaux."""
        res = client.get("/")

        assert res.headers["Server-Timing"].startswith("app;dur=")

    def test_hors_requete_l_identifiant_a_une_valeur_neutre(self):
        """Un journal ecrit au demarrage ou en tache de fond reste valide."""
        assert id_requete() == "-"


class TestJournalStructure:
    def _ligne(self, **champs):
        enregistrement = logging.LogRecord(
            name="hanabi.test", level=logging.INFO, pathname="", lineno=0,
            msg="commande creee", args=(), exc_info=None,
        )
        for cle, valeur in champs.items():
            setattr(enregistrement, cle, valeur)
        return json.loads(FormatJSON().format(enregistrement))

    def test_la_sortie_est_du_json_valide(self):
        ligne = self._ligne()

        assert ligne["message"] == "commande creee"
        assert ligne["niveau"] == "INFO"
        assert ligne["journal"] == "hanabi.test"

    def test_les_champs_metier_sont_conserves(self):
        """C'est tout l'interet du format : retrouver toutes les commandes par
        une recherche sur un champ, plutot que par une expression reguliere sur
        du texte libre."""
        ligne = self._ligne(numero="ATL123456", total_cents=4900)

        assert ligne["numero"] == "ATL123456"
        assert ligne["total_cents"] == 4900

    def test_un_champ_non_serialisable_ne_fait_pas_echouer_le_journal(self):
        """Un journal ne doit jamais casser la requete qu'il decrit."""
        ligne = self._ligne(objet=object())

        assert isinstance(ligne["objet"], str)

    def test_l_exception_est_jointe(self):
        try:
            raise ValueError("panne simulee")
        except ValueError:
            import sys

            enregistrement = logging.LogRecord(
                name="t", level=logging.ERROR, pathname="", lineno=0,
                msg="echec", args=(), exc_info=sys.exc_info(),
            )
            ligne = json.loads(FormatJSON().format(enregistrement))

        assert "panne simulee" in ligne["exception"]


class TestAdresseTronquee:
    """Un journal portant une adresse complete est une donnee personnelle.

    On garde de quoi reconnaitre une source abusive, pas de quoi suivre une
    personne.
    """

    def test_une_adresse_v4_est_reduite_a_son_reseau(self):
        assert _reseau("203.0.113.42") == "203.0.113.0/24"

    def test_une_adresse_v6_est_reduite(self):
        assert _reseau("2001:db8:1234:5678:9abc:def0:1234:5678").endswith("::/64")

    def test_une_adresse_absente_ne_casse_rien(self):
        assert _reseau("") == "-"
