"""Banc d'essai de la recherche du catalogue.

Chaque requête de `requetes.json` attend des objets précis. Une requête réussit
quand tous ses objets attendus figurent dans les k premiers résultats, avec
k = max(3, nombre d'attendus). Deux familles sont plus strictes : « prix »
exige exactement les objets attendus (un objet hors budget est une faute), et
« vide » exige une liste vide.

Deux séries : `reglage.json` sert à régler seuils et textes, `controle.json`
ne sert qu'à mesurer. Régler sur la seconde la rendrait aussi optimiste que
la première.

Lancement, depuis hanabi-back : python tests/recherche/banc.py [--sans-modele]
"""
import json
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

DOSSIER = Path(__file__).parent
SERIES = ("reglage", "controle")

Chercheur = Callable[[str, str], list[str]]


@dataclass
class Resultat:
    famille: str
    q: str
    lang: str
    attendus: list[str]
    obtenus: list[str]
    reussi: bool
    rappel: float


@dataclass
class Rapport:
    resultats: list[Resultat] = field(default_factory=list)

    def taux(self, famille: str | None = None) -> float:
        choisis = [r for r in self.resultats if famille in (None, r.famille)]
        return sum(r.reussi for r in choisis) / len(choisis) if choisis else 0.0

    def rappel(self, famille: str | None = None) -> float:
        choisis = [r for r in self.resultats if r.attendus and famille in (None, r.famille)]
        return sum(r.rappel for r in choisis) / len(choisis) if choisis else 0.0

    def familles(self) -> list[str]:
        return list(dict.fromkeys(r.famille for r in self.resultats))


def charger(serie: str) -> list[dict]:
    return json.loads((DOSSIER / f"{serie}.json").read_text(encoding="utf-8"))["requetes"]


def juger(famille: str, attendus: list[str], obtenus: list[str]) -> tuple[bool, float]:
    if famille == "vide":
        return not obtenus, 1.0
    if famille == "prix":
        trouves = len(set(attendus) & set(obtenus))
        return set(obtenus) == set(attendus), trouves / len(attendus)
    tete = obtenus[: max(3, len(attendus))]
    trouves = sum(code in tete for code in attendus)
    return trouves == len(attendus), trouves / len(attendus)


def mesurer(chercher: Chercheur, serie: str = "reglage") -> Rapport:
    rapport = Rapport()
    for r in charger(serie):
        obtenus = chercher(r["q"], r["lang"])
        reussi, rappel = juger(r["famille"], r["attendus"], obtenus)
        rapport.resultats.append(
            Resultat(r["famille"], r["q"], r["lang"], r["attendus"], obtenus, reussi, rappel)
        )
    return rapport


def chercheur_api(client) -> Chercheur:
    """La recherche telle que la boutique l'appelle, par la route publique."""

    def chercher(q: str, lang: str) -> list[str]:
        reponse = client.get("/products", params={"q": q, "lang": lang, "sort": "pertinence"})
        reponse.raise_for_status()
        return [p["code"] for p in reponse.json()]

    return chercher


def afficher(rapport: Rapport) -> str:
    lignes = []
    par_famille = defaultdict(list)
    for r in rapport.resultats:
        par_famille[r.famille].append(r)
    for famille in rapport.familles():
        lignes.append(f"\n{famille}")
        for r in par_famille[famille]:
            marque = "ok " if r.reussi else "   "
            obtenus = ", ".join(r.obtenus[:5]) or "rien"
            lignes.append(f"  {marque} [{r.lang}] {r.q!r} : {obtenus}")
    lignes.append("\nfamille        réussite   rappel")
    for famille in rapport.familles():
        rappel = "" if famille == "vide" else f"{rapport.rappel(famille):6.0%}"
        lignes.append(f"  {famille:<12} {rapport.taux(famille):6.0%}   {rappel}")
    lignes.append(f"  {'ensemble':<12} {rapport.taux():6.0%}   {rapport.rappel():6.0%}")
    return "\n".join(lignes)


def _client_catalogue(semantique: bool):
    """Base SQLite en mémoire, remplie par le jeu de départ de la boutique."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import plongement
    from app.config import settings
    from app.database import Base, get_db
    from app.main import app
    from app.seed import seed

    settings.RECHERCHE_SEMANTIQUE = semantique
    if semantique and plongement.encodeur(attendre=True) is None:
        sys.exit("Modèle absent : python -m app.plongement, ou --sans-modele")

    moteur = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(moteur)
    session = sessionmaker(bind=moteur)()
    seed(session)
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.stdout.reconfigure(encoding="utf-8")
    chercher = chercheur_api(_client_catalogue(semantique="--sans-modele" not in sys.argv))
    for serie in SERIES:
        print(f"\n=== {serie} ===")
        print(afficher(mesurer(chercher, serie)))
