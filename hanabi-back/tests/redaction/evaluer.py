"""Évaluation de l'assistant de fiche produit contre un vrai fournisseur.

Hors de la suite de tests : elle coûte un appel par objet. Lancement, depuis
hanabi-back, avec REDACTION_URL, REDACTION_CLE et REDACTION_MODELE posées :

    python tests/redaction/evaluer.py

Pour chaque objet du catalogue de départ, l'assistant reçoit ce qu'un marchand
lui donnerait : le nom, la catégorie, la photo et l'accroche en guise de notes.
Deux mesures :

1. Les règles de la fiche : longueur de l'accroche, nombre d'usages, et aucun
   nombre absent des notes (une dimension inventée est le défaut le plus grave).
2. La recherche : le banc est rejoué avec les usages rédigés par l'assistant à
   la place de ceux écrits à la main. S'il fait aussi bien, il peut remplir les
   fiches des objets à venir.
"""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

from app import plongement, recherche, redaction  # noqa: E402
from app.seed import PHOTOS, PRODUCTS  # noqa: E402
from app.translations import PRODUCT_I18N  # noqa: E402
from app.usages import USAGES  # noqa: E402
from recherche.banc import SERIES, charger, juger  # noqa: E402

SORTIE = RACINE / "var" / "evaluation-redaction.json"


def _nombres(texte: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", texte))


def _controler(notes: str, proposition: redaction.Proposition) -> list[str]:
    defauts = []
    connus = _nombres(notes)
    for langue in redaction.LANGUES:
        fiche = getattr(proposition, langue)
        if len(fiche.blurb) > 120:
            defauts.append(f"{langue} : accroche de {len(fiche.blurb)} caractères")
        if not 3 <= len(fiche.usages) <= 4:
            defauts.append(f"{langue} : {len(fiche.usages)} usages")
        texte = " ".join([fiche.name, fiche.blurb, *fiche.usages, fiche.alt])
        inventes = _nombres(texte) - connus
        if inventes:
            defauts.append(f"{langue} : nombres absents des notes {sorted(inventes)}")
    return defauts


def _produit(i, code, nom, categorie, accroche, prix, usages_fr, traductions):
    return SimpleNamespace(
        id=i, code=code, name=nom, category=categorie, blurb=accroche, price_cents=prix,
        usages=usages_fr, alt="", traductions=json.dumps(traductions, ensure_ascii=False),
    )


def _banc(produits, encodeur) -> dict[str, int]:
    recherche.INDEX = recherche.Index()
    fiches = [recherche.fiche(p) for p in produits]
    code = {f.id: f.code for f in fiches}
    scores = {}
    for serie in SERIES:
        requetes = charger(serie)
        scores[serie] = sum(
            juger(r["famille"], r["attendus"], [code[i] for i in recherche.chercher(fiches, r["q"], encodeur)])[0]
            for r in requetes
        )
    return scores


def main() -> None:
    if not redaction.configure():
        sys.exit("REDACTION_URL, REDACTION_CLE et REDACTION_MODELE doivent être posées.")
    encodeur = plongement.encodeur(attendre=True)
    if encodeur is None:
        sys.exit("Modèle de recherche absent : python -m app.plongement")

    a_la_main, par_l_assistant, rapport = [], [], []
    for i, (code, nom, categorie, accroche, prix, *_ ) in enumerate(PRODUCTS):
        a_la_main.append(_produit(i, code, nom, categorie, accroche, prix, USAGES[code], PRODUCT_I18N[code]))
        demande = redaction.Demande(name=nom, category=categorie, notes=accroche, image=PHOTOS[code])
        try:
            resultat = redaction.rediger(demande, exemples=[])
        except redaction.ErreurRedaction as e:
            rapport.append({"code": code, "erreur": e.message})
            print(f"{code} {nom} : échec, {e.message}")
            continue
        p = resultat.proposition
        defauts = _controler(accroche, p)
        traductions = {
            langue: {**PRODUCT_I18N[code][langue], "usages": "\n".join(getattr(p, langue).usages)}
            for langue in ("en", "es")
        }
        par_l_assistant.append(_produit(i, code, nom, categorie, accroche, prix, "\n".join(p.fr.usages), traductions))
        rapport.append({
            "code": code, "photo_lue": resultat.photo_lue, "categorie_juste": p.categorie == categorie,
            "defauts": defauts, "proposition": p.model_dump(),
        })
        print(f"{code} {nom} : {'photo lue' if resultat.photo_lue else 'sans photo'}, "
              f"catégorie {'juste' if p.categorie == categorie else p.categorie}, "
              f"{len(defauts)} défaut(s) {defauts or ''}")

    main_scores = _banc(a_la_main, encodeur)
    # Un objet sans proposition garde ses usages écrits à la main
    rediges = {p.code for p in par_l_assistant}
    melange = par_l_assistant + [p for p in a_la_main if p.code not in rediges]
    assistant_scores = _banc(melange, encodeur)

    print("\nrequêtes réussies      réglage   contrôle")
    print(f"  usages à la main       {main_scores['reglage']:>5}   {main_scores['controle']:>8}")
    print(f"  usages de l'assistant  {assistant_scores['reglage']:>5}   {assistant_scores['controle']:>8}")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({
        "modele": redaction.settings.REDACTION_MODELE,
        "banc": {"a_la_main": main_scores, "assistant": assistant_scores},
        "objets": rapport,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDétail : {SORTIE}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
