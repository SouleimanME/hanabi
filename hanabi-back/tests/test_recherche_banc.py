"""Banc d'essai de la recherche, rejoué sur le catalogue de départ.

Les planchers ne descendent jamais : une recherche qui améliore le banc les
relève. Ce sont des nombres de réussites, et non des taux : ajouter des
requêtes ne les fausse pas.

La recherche par le sens demande le modèle (python -m app.plongement). Sans
lui, ses tests sont sautés, sauf si RECHERCHE_EXIGEE est posée : le job de CI
qui télécharge le modèle ne peut pas les sauter en silence.
"""
import os

import pytest

from app import plongement
from app.config import settings
from app.seed import seed
from recherche.banc import afficher, chercheur_api, mesurer

# Recherche par sous-chaîne d'avant : 11 sur 36 en réglage, 14 sur 37 en contrôle
PLANCHERS_TEXTE = {"reglage": 27, "controle": 25}
PLANCHERS_SENS = {"reglage": 31, "controle": 30}


def _modele_ou_saut():
    if plongement.encodeur(attendre=True) is None:
        if os.environ.get("RECHERCHE_EXIGEE"):
            pytest.fail("RECHERCHE_EXIGEE posée, mais le modèle ne se charge pas")
        pytest.skip("modèle absent : python -m app.plongement")


@pytest.fixture
def chercheur(client, db_session):
    seed(db_session)
    return chercheur_api(client)


@pytest.fixture
def chercheur_sens(chercheur, monkeypatch):
    _modele_ou_saut()
    monkeypatch.setattr(settings, "RECHERCHE_SEMANTIQUE", True)
    return chercheur


@pytest.mark.parametrize("serie", ["reglage", "controle"])
def test_par_le_texte(chercheur, serie):
    rapport = mesurer(chercheur, serie)
    assert rapport.taux("exacte") == 1.0, afficher(rapport)
    assert rapport.taux("vide") == 1.0, afficher(rapport)
    reussites = sum(r.reussi for r in rapport.resultats)
    assert reussites >= PLANCHERS_TEXTE[serie], afficher(rapport)


@pytest.mark.parametrize("serie", ["reglage", "controle"])
def test_par_le_sens(chercheur_sens, serie):
    rapport = mesurer(chercheur_sens, serie)
    assert rapport.taux("exacte") == 1.0, afficher(rapport)
    # Le risque propre au sens : répondre quelque chose à « pizza »
    assert rapport.taux("vide") == 1.0, afficher(rapport)
    reussites = sum(r.reussi for r in rapport.resultats)
    assert reussites >= PLANCHERS_SENS[serie], afficher(rapport)
