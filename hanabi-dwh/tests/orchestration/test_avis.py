# -*- coding: utf-8 -*-
"""Analyse des avis, sans base ni fournisseur.

    python -m unittest discover -s tests/orchestration
"""

import io
import json
import os
import unittest
import urllib.error

os.environ.setdefault("DWH_DATABASE_URL", "postgresql://factice:factice@localhost:5999/factice")

from ingestion import avis  # noqa: E402
from ingestion.avis import LOT, THEMES, analyser, appeler, consigne, lire, messages  # noqa: E402
from tests.avis.mesure import Score, noter  # noqa: E402


def _reponse(*entrees) -> str:
    return json.dumps({"avis": list(entrees)})


def _sans_pause(_):
    pass


class FauxFournisseur:
    """Rend les réponses données, dans l'ordre, et garde les messages reçus."""

    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.recus = []

    def __call__(self, historique):
        self.recus.append(historique)
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


class Lecture(unittest.TestCase):
    def test_couples_valides(self):
        lus = lire(_reponse({"n": 1, "themes": [{"theme": "livraison", "ton": "negatif"}]}), 1)
        self.assertEqual(lus, {1: [("livraison", "negatif")]})

    def test_un_theme_hors_liste_est_ecarte_pas_l_avis(self):
        lus = lire(_reponse({"n": 1, "themes": [
            {"theme": "odeur", "ton": "negatif"},
            {"theme": "prix", "ton": "neutre"},
            {"theme": "qualite", "ton": "positif"},
        ]}), 1)
        self.assertEqual(lus, {1: [("qualite", "positif")]})

    def test_un_theme_compte_une_fois(self):
        lus = lire(_reponse({"n": 1, "themes": [
            {"theme": "qualite", "ton": "positif"},
            {"theme": "qualite", "ton": "negatif"},
        ]}), 1)
        self.assertEqual(lus[1], [("qualite", "positif")])

    def test_numeros_hors_du_lot_ignores(self):
        lus = lire(_reponse({"n": 0, "themes": []}, {"n": 3, "themes": []}, {"n": 2, "themes": []}), 2)
        self.assertEqual(set(lus), {2})

    def test_eloge_general_liste_vide(self):
        self.assertEqual(lire(_reponse({"n": 1, "themes": []}), 1), {1: []})

    def test_json_entoure_de_texte(self):
        contenu = "Voici :\n```json\n" + _reponse({"n": 1, "themes": []}) + "\n```"
        self.assertEqual(lire(contenu, 1), {1: []})

    def test_forme_invalide(self):
        with self.assertRaises(ValueError):
            lire('{"resultats": []}', 1)
        with self.assertRaises(ValueError):
            lire("rien", 1)


class Consigne(unittest.TestCase):
    def test_liste_fermee_ecrite_dans_la_consigne(self):
        texte = consigne()
        for theme in THEMES:
            self.assertIn(f"- {theme} :", texte)

    def test_seul_le_texte_part(self):
        contenu = messages(["Colis égaré"])[1]["content"]
        self.assertIn('{"n": 1, "texte": "Colis égaré"}', contenu)


class Analyse(unittest.TestCase):
    def test_par_lots(self):
        textes = {f"e{i}": f"avis {i}" for i in range(LOT + 3)}
        faux = FauxFournisseur(
            _reponse(*({"n": n, "themes": []} for n in range(1, LOT + 1))),
            _reponse(*({"n": n, "themes": [{"theme": "prix", "ton": "positif"}]} for n in range(1, 4))),
        )
        bilan = analyser(textes, faux, _sans_pause)
        self.assertEqual(bilan.appels, 2)
        self.assertEqual(len(bilan.analyses), LOT + 3)
        self.assertEqual(bilan.analyses[f"e{LOT}"], [("prix", "positif")])
        self.assertEqual(bilan.manques, 0)

    def test_une_reponse_illisible_est_redemandee_une_fois(self):
        faux = FauxFournisseur("pas du JSON", _reponse({"n": 1, "themes": []}))
        bilan = analyser({"e": "Parfait."}, faux, _sans_pause)
        self.assertEqual(bilan.analyses, {"e": []})
        self.assertIn("Réponse invalide", faux.recus[1][-1]["content"])

    def test_deux_reponses_illisibles_laissent_le_lot_pour_plus_tard(self):
        faux = FauxFournisseur("non", "toujours pas")
        bilan = analyser({"e": "Parfait."}, faux, _sans_pause)
        self.assertEqual(bilan.analyses, {})
        self.assertEqual(bilan.manques, 1)

    def test_un_avis_oublie_est_compte_manquant(self):
        faux = FauxFournisseur(_reponse({"n": 1, "themes": []}))
        bilan = analyser({"a": "un", "b": "deux"}, faux, _sans_pause)
        self.assertEqual(set(bilan.analyses), {"a"})
        self.assertEqual(bilan.manques, 1)

    def test_une_panne_garde_ce_qui_est_lu(self):
        textes = {f"e{i}": "x" for i in range(LOT + 1)}
        panne = urllib.error.HTTPError("https://x", 503, "indisponible", {}, io.BytesIO(b""))
        faux = FauxFournisseur(_reponse(*({"n": n, "themes": []} for n in range(1, LOT + 1))), panne)
        bilan = analyser(textes, faux, _sans_pause)
        self.assertEqual(len(bilan.analyses), LOT)
        self.assertEqual(bilan.manques, 1)
        self.assertIn("503", bilan.erreur)


class Appel(unittest.TestCase):
    def setUp(self):
        os.environ.update(REDACTION_MODELE="modele-test")

    def test_temperature_nulle_et_json_demande(self):
        corps = []
        appeler([], lambda c: corps.append(c) or {"choices": [{"message": {"content": "{}"}}]})
        self.assertEqual(corps[0]["temperature"], 0)
        self.assertEqual(corps[0]["response_format"], {"type": "json_object"})

    def test_refus_pour_debit_retente_apres_le_delai(self):
        attentes = []
        reponses = [
            urllib.error.HTTPError("https://x", 429, "trop", {"Retry-After": "1"}, io.BytesIO(b"")),
            {"choices": [{"message": {"content": "ok"}}]},
        ]

        def envoyer(_):
            r = reponses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        self.assertEqual(appeler([], envoyer, attentes.append), "ok")
        self.assertEqual(attentes, [1.0])


class Mesure(unittest.TestCase):
    def test_bon_theme_mauvais_ton_compte_faux_et_manque(self):
        score = Score()
        ecarts = noter({"attendu": [["livraison", "negatif"]]}, [("livraison", "positif")], score)
        self.assertEqual((score.justes, score.faux, score.manques), (0, 1, 1))
        self.assertEqual(ecarts["faux"], [("livraison", "positif")])

    def test_tolere_ni_juste_ni_faux(self):
        score = Score()
        reference = {"attendu": [["conformite", "positif"]], "tolere": [["esthetique", "positif"]]}
        noter(reference, [("conformite", "positif"), ("esthetique", "positif")], score)
        self.assertEqual((score.justes, score.faux, score.manques), (1, 0, 0))
        self.assertEqual(score.avis_exacts, 1)

    def test_rien_attendu_rien_rendu_est_exact(self):
        score = Score()
        noter({"attendu": []}, [], score)
        self.assertEqual(score.avis_exacts, 1)
        self.assertEqual(score.f1, 1.0)


class References(unittest.TestCase):
    def test_references_dans_la_liste_fermee(self):
        with open(os.path.join("tests", "avis", "references.json"), encoding="utf-8") as f:
            references = json.load(f)["avis"]
        textes = [r["texte"] for r in references]
        self.assertEqual(len(textes), len(set(textes)))
        for r in references:
            for theme, ton in r["attendu"] + r.get("tolere", []):
                self.assertIn(theme, THEMES, r["texte"])
                self.assertIn(ton, avis.TONS, r["texte"])
            # Un couple ne peut être à la fois attendu et toléré
            self.assertFalse({tuple(c) for c in r["attendu"]} & {tuple(c) for c in r.get("tolere", [])})


class Branchement(unittest.TestCase):
    def test_en_amont_de_dbt(self):
        import dagster as dg

        from orchestration import defs

        graphe = defs.resolve_asset_graph()
        enfants = graphe.get(dg.AssetKey(["externe", "analyses_avis"])).child_keys
        self.assertIn(dg.AssetKey(["bronze", "brz_analyses_avis"]), enfants)
        parents = graphe.get(dg.AssetKey(["externe", "analyses_avis"])).parent_keys
        self.assertIn(dg.AssetKey(["public", "reviews"]), parents)


if __name__ == "__main__":
    unittest.main()
