"""Banc du conseiller cadeau : ce que le serveur montre au modèle.

Le modèle ne choisit que parmi les candidats ; leur sélection se mesure donc
sans fournisseur. Trois exigences : le budget toujours respecté, rien en
stock nul, et un objet acceptable parmi les trois premiers candidats. Le
plancher ne descend jamais.
"""
import json
import os
from pathlib import Path

import pytest

from app import conseil, plongement, recherche
from app.seed import seed

DEMANDES = json.loads((Path(__file__).parent / "conseil" / "demandes.json").read_text(encoding="utf-8"))["demandes"]
# Mesuré à la création du conseiller, sur 19 demandes
PLANCHERS = {"texte": 18, "sens": 18}


def _mesurer(db, encodeur):
    reussites, echecs = 0, []
    for d in DEMANDES:
        candidats = conseil.candidats(db, d["demande"], encodeur)
        codes = [p.code for p in candidats]
        assert all(p.stock > 0 for p in candidats), d["demande"]
        assert all(p.price_cents <= d.get("budget", 10**9) for p in candidats), (d["demande"], codes)
        succes = bool(set(codes[:3]) & set(d["acceptables"])) if d["acceptables"] else not codes
        reussites += succes
        if not succes:
            echecs.append(f"{d['demande']} : {codes[:3]}")
    return reussites, echecs


@pytest.fixture
def boutique(db_session, monkeypatch):
    monkeypatch.setattr(recherche, "INDEX", recherche.Index())
    seed(db_session)
    return db_session


def test_par_le_texte(boutique):
    reussites, echecs = _mesurer(boutique, None)
    assert reussites >= PLANCHERS["texte"], echecs


def test_par_le_sens(boutique):
    encodeur = plongement.encodeur(attendre=True)
    if encodeur is None:
        if os.environ.get("RECHERCHE_EXIGEE"):
            pytest.fail("RECHERCHE_EXIGEE posée, mais le modèle ne se charge pas")
        pytest.skip("modèle absent : python -m app.plongement")
    reussites, echecs = _mesurer(boutique, encodeur)
    assert reussites >= PLANCHERS["sens"], echecs
