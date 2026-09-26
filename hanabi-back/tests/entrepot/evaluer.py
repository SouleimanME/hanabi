"""Évaluation de « Demander à l'entrepôt » contre un vrai fournisseur.

Hors de la suite : un appel par question, sur un entrepôt construit
(PostgreSQL). Lancement, depuis hanabi-back, avec DATABASE_URL vers la base de
l'entrepôt et REDACTION_URL, REDACTION_CLE, REDACTION_MODELE posées :

    python tests/entrepot/evaluer.py

Pour chaque question : la requête du modèle rend-elle le même résultat que la
référence (voir comparer.py), et les questions à refuser le sont-elles, sans
rien exécuter. Mesure aussi la part de requêtes corrigées après un refus de la
base.
"""
import json
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).parent))

from comparer import meme_reponse  # noqa: E402

from app import fournisseur, question_entrepot, warehouse  # noqa: E402
from app.database import SessionLocal  # noqa: E402

QUESTIONS = json.loads((Path(__file__).parent / "questions.json").read_text(encoding="utf-8"))["questions"]
SORTIE = RACINE / "var" / "evaluation-entrepot.json"
# Entre deux questions : les offres d'entrée de gamme plafonnent à 20 000 jetons par minute
PAUSE = float(os.environ.get("EVAL_PAUSE", "10"))


def main() -> None:
    if not fournisseur.configure():
        sys.exit("REDACTION_URL, REDACTION_CLE et REDACTION_MODELE doivent être posées.")
    db = SessionLocal()
    justes, refus_justes, corrigees, echecs, lignes = 0, 0, 0, 0, []
    a_traiter = [q for q in QUESTIONS if not q.get("refus")]
    for i, q in enumerate(QUESTIONS):
        if i:
            time.sleep(PAUSE)
        try:
            reponse = question_entrepot._traduire_et_executer(db, q["question"])
        except (fournisseur.ErreurFournisseur, question_entrepot.SqlIntraduisible) as e:
            echecs += 1
            lignes.append({"question": q["question"], "erreur": getattr(e, "message", str(e))})
            print(f"échec  {q['question'][:60]}")
            continue
        corrigees += reponse.tentatives == 2
        if q.get("refus"):
            juste = reponse.refus is not None and reponse.resultat is None
            refus_justes += juste
        else:
            reference = warehouse.executer_sql(db, q["sql"], limite=question_entrepot.LIMITE,
                                               schemas=question_entrepot.SCHEMAS)
            juste = reponse.resultat is not None and meme_reponse(
                reference, reponse.resultat, q.get("ordonne", False))
            justes += juste
        lignes.append({"question": q["question"], "juste": juste, "sql": reponse.sql,
                       "refus": reponse.refus, "tentatives": reponse.tentatives})
        print(f"{'ok ' if juste else '   '}   {q['question'][:60]:60} {reponse.sql or reponse.refus}")
    db.close()

    print(f"\nrésultats justes         : {justes}/{len(a_traiter)}")
    print(f"refus justes             : {refus_justes}/{len(QUESTIONS) - len(a_traiter)}")
    print(f"corrigées après un refus : {corrigees}")
    print(f"échecs                   : {echecs}")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({
        "modele": fournisseur.settings.REDACTION_MODELE, "justes": justes, "sur": len(a_traiter),
        "refus_justes": refus_justes, "corrigees": corrigees, "echecs": echecs, "questions": lignes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDétail : {SORTIE}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
