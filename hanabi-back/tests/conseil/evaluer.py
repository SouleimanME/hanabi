"""Évaluation du conseiller cadeau contre un vrai fournisseur.

Hors de la suite de tests : elle coûte un appel par demande. Lancement, depuis
hanabi-back, avec REDACTION_URL, REDACTION_CLE et REDACTION_MODELE posées :

    python tests/conseil/evaluer.py

Pour chaque demande de `demandes.json` : la réponse est-elle valide, le premier
objet proposé est-il acceptable, l'un d'eux l'est-il, et une demande sans
réponse possible reste-t-elle sans objet. Le budget et le stock ne se mesurent
pas ici : le serveur les garantit avant d'appeler le modèle (voir
test_conseil_banc.py).
"""
import json
import os
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import conseil, fournisseur, plongement  # noqa: E402
from app.database import Base  # noqa: E402
from app.seed import seed  # noqa: E402

DEMANDES = json.loads((Path(__file__).parent / "demandes.json").read_text(encoding="utf-8"))["demandes"]
SORTIE = RACINE / "var" / "evaluation-conseil.json"
# Entre deux demandes : les offres d'entrée de gamme plafonnent à 20 000 jetons par minute
PAUSE = float(os.environ.get("EVAL_PAUSE", "10"))


def main() -> None:
    if not fournisseur.configure():
        sys.exit("REDACTION_URL, REDACTION_CLE et REDACTION_MODELE doivent être posées.")
    moteur = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(moteur)
    db = sessionmaker(bind=moteur)()
    seed(db)
    encodeur = plongement.encodeur(attendre=True)

    lignes, premier, un_des, vides_justes, echecs, durees = [], 0, 0, 0, 0, []
    avec_objets = [d for d in DEMANDES if d["acceptables"]]
    for i, d in enumerate(DEMANDES):
        if i:
            time.sleep(PAUSE)
        debut = time.monotonic()
        try:
            resultat = conseil.conseiller(db, d["demande"], d["lang"], encodeur)
        except fournisseur.ErreurFournisseur as e:
            echecs += 1
            lignes.append({"demande": d["demande"], "erreur": e.message})
            print(f"échec   {d['demande'][:60]} : {e.message}")
            continue
        durees.append(time.monotonic() - debut)
        codes = [p.code for p, _ in resultat.choix]
        if d["acceptables"]:
            premier += bool(codes) and codes[0] in d["acceptables"]
            un_des += bool(set(codes) & set(d["acceptables"]))
        else:
            vides_justes += not codes
        lignes.append({
            "demande": d["demande"], "acceptables": d["acceptables"], "message": resultat.message,
            "choix": [{"code": p.code, "raison": r} for p, r in resultat.choix],
        })
        print(f"{'ok ' if set(codes) & set(d['acceptables']) or (not d['acceptables'] and not codes) else '   '}"
              f"     {d['demande'][:60]:60} {codes}")

    n = len(avec_objets)
    print(f"\npremier objet acceptable : {premier}/{n}")
    print(f"un objet acceptable      : {un_des}/{n}")
    print(f"sans objet quand il faut : {vides_justes}/{len(DEMANDES) - n}")
    print(f"échecs du fournisseur    : {echecs}/{len(DEMANDES)}")
    if durees:
        print(f"durée médiane            : {sorted(durees)[len(durees) // 2]:.1f} s")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({
        "modele": fournisseur.settings.REDACTION_MODELE,
        "premier": premier, "un_des": un_des, "sur": n, "vides_justes": vides_justes, "echecs": echecs,
        "demandes": lignes,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDétail : {SORTIE}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
