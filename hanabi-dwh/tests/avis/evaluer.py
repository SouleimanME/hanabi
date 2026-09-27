# -*- coding: utf-8 -*-
"""Évaluation de l'analyse des avis contre un vrai fournisseur.

Demande REDACTION_URL, REDACTION_CLE et REDACTION_MODELE, pas de base :

    python tests/avis/evaluer.py                       banc de référence, consigne actuelle
    python tests/avis/evaluer.py --jeu controle        avis mitigés
    python tests/avis/evaluer.py --jeu controle --version 1

Écrit le détail dans var/evaluation-avis-<jeu>-v<version>.json et affiche le résumé.
"""

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from ingestion.avis import CONSIGNES, VERSION, analyser, appeler, configure  # noqa: E402
from tests.avis.mesure import Score, noter  # noqa: E402

JEUX = {"references": "references.json", "controle": "controle.json"}

# Le seuil fixé avant la première mesure : en dessous, les thèmes ne sont pas
# assez fiables pour qu'un tableau de bord les compte
SEUIL_F1 = 0.80


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Évaluation de l'analyse des avis.")
    p.add_argument("--jeu", choices=sorted(JEUX), default="references")
    p.add_argument("--version", choices=sorted(CONSIGNES), default=VERSION)
    args = p.parse_args()
    if not configure():
        print("REDACTION_URL, REDACTION_CLE et REDACTION_MODELE sont requises.")
        return 2
    fichier = Path(__file__).parent / JEUX[args.jeu]
    references = json.loads(fichier.read_text(encoding="utf-8"))["avis"]
    textes = {str(i): r["texte"] for i, r in enumerate(references)}
    bilan = analyser(textes, appeler, version=args.version)
    if bilan.erreur:
        print(f"Analyse interrompue : {bilan.erreur}")
        return 1

    score = Score()
    details = []
    for i, reference in enumerate(references):
        rendu = bilan.analyses.get(str(i))
        if rendu is None:
            details.append({"texte": reference["texte"], "absent": True})
            noter(reference, [], score)
            continue
        ecarts = noter(reference, rendu, score)
        if ecarts["faux"] or ecarts["manques"]:
            details.append({"texte": reference["texte"], "rendu": rendu, **ecarts})

    resume = {
        "jeu": args.jeu,
        "version": args.version,
        "avis": score.avis,
        "avis_exacts": score.avis_exacts,
        "precision": round(score.precision, 3),
        "rappel": round(score.rappel, 3),
        "f1": round(score.f1, 3),
        "appels": bilan.appels,
        "manques_de_reponse": bilan.manques,
    }
    sortie = RACINE / "var" / f"evaluation-avis-{args.jeu}-v{args.version}.json"
    sortie.parent.mkdir(exist_ok=True)
    sortie.write_text(
        json.dumps({"resume": resume, "ecarts": details}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(resume, ensure_ascii=False, indent=2))
    print(f"Détail des écarts : {sortie}")
    return 0 if score.f1 >= SEUIL_F1 else 1


if __name__ == "__main__":
    sys.exit(main())
