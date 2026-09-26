"""Les requêtes de référence de `questions.json` tournent-elles sur l'entrepôt ?

Lancé par la CI après la construction de l'entrepôt, sans fournisseur : un
renommage de colonne dans dbt casserait sinon le banc en silence. Chaque
requête passe par la console, limitée à gold, comme celles du modèle. Vérifie
aussi que le schéma montré au modèle décrit toutes les tables d'agrégats.

    DATABASE_URL=postgresql://... python tests/entrepot/verifier_references.py
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from app import question_entrepot, warehouse  # noqa: E402
from app.database import SessionLocal  # noqa: E402

QUESTIONS = json.loads((Path(__file__).parent / "questions.json").read_text(encoding="utf-8"))["questions"]


def main() -> int:
    db = SessionLocal()
    echecs = []
    schema = question_entrepot.contexte(db)
    for mart in warehouse.MARTS:
        if f"gold.{mart.table} :" not in schema:
            echecs.append(f"schéma : {mart.table} absente de ce que voit le modèle")
    for q in QUESTIONS:
        if q.get("refus"):
            continue
        try:
            resultat = warehouse.executer_sql(db, q["sql"], limite=question_entrepot.LIMITE,
                                              schemas=question_entrepot.SCHEMAS)
        except warehouse.SqlRefuse as refus:
            echecs.append(f"{q['question']} : {refus}")
            continue
        print(f"{resultat['total']:>4} ligne(s)  {q['question']}")
    db.close()
    for echec in echecs:
        print("ÉCHEC", echec)
    print(f"\n{len(echecs)} échec(s), schéma de {len(schema)} caractères")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
