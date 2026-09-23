# -*- coding: utf-8 -*-
"""Verdicts des contrôles de volume et de fraîcheur, sans base de données.

    python -m unittest discover -s tests/orchestration
"""

import datetime as dt
import os
import unittest

# Sans URL explicite, `ressources.py` irait lire le .env de l'API
os.environ.setdefault("DWH_DATABASE_URL", "postgresql://factice:factice@localhost:5999/factice")

from orchestration.controles import (  # noqa: E402
    CONTROLES,
    controles_volume_fraicheur,
    juge_calendrier,
    juge_commandes,
    juge_fraicheur,
)

J = dt.date(2026, 9, 18)


class Commandes(unittest.TestCase):
    def test_premiere_mesure_sans_reference(self):
        v = juge_commandes(843, None)
        self.assertTrue(v.reussi)
        self.assertEqual(v.attendu, "aucune référence")

    def test_egal_au_plus_haut(self):
        self.assertTrue(juge_commandes(843, 843).reussi)

    def test_une_baisse_echoue_et_dit_combien(self):
        v = juge_commandes(840, 843)
        self.assertFalse(v.reussi)
        self.assertIn("3 commandes ont disparu", v.message)

    def test_milliers_separes_comme_dans_le_back_office(self):
        v = juge_commandes(58_883, 58_888)
        self.assertEqual(v.attendu, "au moins 58 888")
        self.assertIn("(58 888)", v.message)


class Calendrier(unittest.TestCase):
    def test_serie_complete_jusqu_a_aujourd_hui(self):
        v = juge_calendrier(730, J - dt.timedelta(days=729), J, J)
        self.assertTrue(v.reussi)

    def test_un_jour_manquant(self):
        v = juge_calendrier(729, J - dt.timedelta(days=729), J, J)
        self.assertFalse(v.reussi)
        self.assertIn("1 jour sans ligne", v.message)

    def test_serie_arretee_avant_aujourd_hui(self):
        hier = J - dt.timedelta(days=1)
        v = juge_calendrier(730, hier - dt.timedelta(days=729), hier, J)
        self.assertFalse(v.reussi)
        self.assertIn("s'arrête", v.message)

    def test_table_vide(self):
        self.assertFalse(juge_calendrier(0, None, None, J).reussi)


class Fraicheur(unittest.TestCase):
    def test_aujourd_hui(self):
        v = juge_fraicheur(J, J, 3, "vente")
        self.assertTrue(v.reussi)
        self.assertIn("aujourd'hui", v.message)

    def test_a_la_limite(self):
        self.assertTrue(juge_fraicheur(J - dt.timedelta(days=3), J, 3, "vente").reussi)

    def test_au_dela(self):
        v = juge_fraicheur(J - dt.timedelta(days=6), J, 5, "cotation")
        self.assertFalse(v.reussi)
        self.assertEqual(v.valeur, 6)

    def test_rien_en_base(self):
        self.assertFalse(juge_fraicheur(None, J, 3, "vente").reussi)


class Branchement(unittest.TestCase):
    def test_seules_les_erreurs_bloquent(self):
        specs = {spec.name: spec for spec in controles_volume_fraicheur.check_specs}
        self.assertEqual(set(specs), {nom for nom, *_ in CONTROLES})
        for nom, _titre, _famille, _modele, gravite in CONTROLES:
            self.assertEqual(specs[nom].blocking, gravite == "erreur", nom)

    def test_rattaches_aux_modeles_dbt(self):
        cles = {spec.name: spec.asset_key.path[-1] for spec in controles_volume_fraicheur.check_specs}
        self.assertEqual(cles["commandes_jamais_en_baisse"], "slv_commandes")
        self.assertEqual(cles["dernier_taux"], "brz_taux_change")


if __name__ == "__main__":
    unittest.main()
