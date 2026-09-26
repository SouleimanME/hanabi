"""Recherche du catalogue : par le texte, par le sens et par le prix.

Trois étages, du plus sûr au plus flou :

1. Le prix. « moins de 30 € », « entre 30 et 40 », « under 40 » deviennent un
   filtre, et la phrase est retirée de la requête. Un modèle de sens lit mal
   les nombres ; une expression régulière les lit sans faute.
2. Le texte. Chaque mot de la requête doit se retrouver dans la fiche, à une
   faute de frappe près : « kokechi » trouve « Kokeshi ».
3. Le sens. La requête et chaque fiche deviennent des vecteurs (voir
   `plongement.py`). Un seuil absolu ne marcherait pas : ce modèle donne 0,80
   à « pizza » contre un renard en résine. On mesure donc de combien un objet
   se détache du reste du catalogue pour cette requête, et les mots de la
   requête retrouvés dans sa fiche renforcent cet écart : « regalo zorro »
   se détache peu par le sens, mais « zorro » est dans l'accroche espagnole.

Sans modèle chargé, les deux premiers étages répondent seuls.
"""
import logging
import re
import threading
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache

import numpy as np
from sqlalchemy import select

from . import models, plongement
from .translations import PRODUCT_I18N

log = logging.getLogger("hanabi.recherche")

# Réglés sur tests/recherche/reglage.json, jamais sur controle.json.
# Poids d'une fiche dont tous les mots de la requête se retrouvent, face à
# l'écart de sens au score moyen du catalogue
# (Le banc plafonne sur un plateau, poids de 0,025 à 0,040 et seuil de 0,028 à
# 0,034 : on en prend le centre, le plus loin possible des bords)
POIDS_TEXTE = 0.035
# Score minimal pour qu'un objet soit retenu sans correspondance complète
SEUIL = 0.031

CATEGORIES = {
    "Figurines": ("Figurines", "Figures", "Figuras"),
    "Décoration": ("Décoration", "Decoration", "Decoración"),
    "Luminaires": ("Luminaires", "Lighting", "Iluminación"),
}

# Mots sans contenu, dans les trois langues
VIDES = frozenset(
    """a au aux avec ce ces cet cette d de des du en et l la le les ma mes mon ou par pas
    pour qu que qui sa ses son sur ta tes ton tres un une
    an and for in my of on or that the this to very with your
    al con del el las los mi mis muy o para por su sus una unas uno unos y""".split()
)

# Une requête réduite à ces mots ne restreint rien : « cadeau à moins de 40 € »
GENERIQUES = frozenset(
    """article articles cadeau cadeaux chose idee idees objet objets truc
    gift gifts item items something thing
    algo articulo articulos idea ideas objeto objetos regalo regalos""".split()
)

_NOMBRE = r"(\d+(?:[.,]\d{1,2})?)"
_MONNAIE = r"(?:\s*(?:€|euros?\b|eur\b))?"
_PRIX = [
    # Deux bornes : « entre 30 et 40 € », « de 30 à 40 », « 30-40 € »
    (re.compile(rf"(?:\b(?:entre|between|de|from|desde)\s+)?{_NOMBRE}{_MONNAIE}\s*(?:\bet\b|\band\b|\ba\b|\by\b|\bto\b|-)\s*{_NOMBRE}{_MONNAIE}"), "entre"),
    (re.compile(rf"(?:\bmoins de|\bmax(?:imum)?|\bjusqu ?a|\bpas plus de|\bunder|\bbelow|\bless than|\bup to|\bmenos de|\bhasta|<=?)\s*{_NOMBRE}{_MONNAIE}"), "max"),
    (re.compile(rf"(?:\bplus de|\bau moins|\ba partir de|\bover|\babove|\bmore than|\bmas de|>=?)\s*{_NOMBRE}{_MONNAIE}"), "min"),
]


@dataclass(frozen=True)
class Fiche:
    """Ce que la recherche sait d'un objet, dans les trois langues."""

    id: int
    code: str
    categorie: str
    prix_cents: int
    # (nom, accroche) en français, puis dans chaque traduction
    libelles: tuple[tuple[str, str], ...]
    usages: tuple[str, ...]


def fiche(p) -> Fiche:
    libelles = [(p.name, p.blurb)]
    libelles += [(t["name"], t["blurb"]) for t in PRODUCT_I18N.get(p.code, {}).values()]
    usages = tuple(u.strip() for u in (p.usages or "").splitlines() if u.strip())
    return Fiche(p.id, p.code, p.category, p.price_cents, tuple(libelles), usages)


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, ponctuation en espaces : « Éventail » devient « eventail »."""
    decompose = unicodedata.normalize("NFKD", texte.lower())
    sans = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w€<>=.,-]+", " ", sans).strip()


def _mots(texte: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normaliser(texte))


def _racine(mot: str) -> str:
    for fin in ("es", "s", "x"):
        if len(mot) > 4 and mot.endswith(fin):
            return mot[: -len(fin)]
    return mot


# --- Prix ---


@dataclass(frozen=True)
class Requete:
    texte: str
    prix_min: int | None = None
    prix_max: int | None = None


def _cents(nombre: str) -> int:
    return round(float(nombre.replace(",", ".")) * 100)


def analyser(q: str) -> Requete:
    """Sépare la contrainte de prix du reste de la requête."""
    texte = normaliser(q)
    bas = haut = None
    for motif, sorte in _PRIX:
        m = motif.search(texte)
        if not m:
            continue
        if sorte == "entre":
            bas, haut = sorted((_cents(m.group(1)), _cents(m.group(2))))
        elif sorte == "max":
            haut = _cents(m.group(1))
        else:
            bas = _cents(m.group(1))
        texte = (texte[: m.start()] + " " + texte[m.end():]).strip()
        break
    texte = re.sub(r"(?:€|\beuros?\b|\beur\b)", " ", texte)
    return Requete(" ".join(texte.split()), bas, haut)


# --- Texte ---


@lru_cache(maxsize=20_000)
def _vocabulaire(f: Fiche) -> frozenset[str]:
    textes = [f.code, *CATEGORIES.get(f.categorie, (f.categorie,)), *f.usages]
    for nom, accroche in f.libelles:
        textes += [nom, accroche]
    return frozenset(m for t in textes for m in _mots(t))


@lru_cache(maxsize=20_000)
def _textes_entiers(f: Fiche) -> tuple[str, ...]:
    return tuple(normaliser(t) for t in (f.code, *(x for paire in f.libelles for x in paire)))


def _proche(mot: str, v: str) -> bool:
    if mot == v:
        return True
    # Un mot en cours de frappe : « kits » ; pas « art » pour « artisanat »
    if len(mot) >= 4 and v.startswith(mot):
        return True
    if _racine(v) == _racine(mot):
        return True
    # Une faute de frappe sur un mot assez long : « kokechi », « hanya »
    if len(mot) < 4 or abs(len(v) - len(mot)) > 2:
        return False
    comparaison = SequenceMatcher(None, mot, v)
    return comparaison.quick_ratio() >= 0.8 and comparaison.ratio() >= 0.8


def mots_utiles(texte: str) -> list[str]:
    """Les mots qui portent la requête : ni mots vides, ni « cadeau » s'il y a mieux."""
    mots = [m for m in _mots(texte) if m not in VIDES]
    precis = [m for m in mots if m not in GENERIQUES]
    return precis or mots


def couvertures(fiches: list[Fiche], requete: str) -> np.ndarray:
    """Pour chaque fiche, la part des mots utiles de la requête qu'on y retrouve.

    Chaque mot n'est comparé qu'une fois au vocabulaire de tout le catalogue ;
    une fiche n'a plus qu'à croiser ses mots avec les voisins trouvés. Comparer
    chaque mot à chaque fiche coûtait une demi-seconde pour mille objets.
    """
    mots = mots_utiles(requete)
    if not mots or not fiches:
        return np.zeros(len(fiches))
    vocabulaires = [_vocabulaire(f) for f in fiches]
    catalogue = frozenset().union(*vocabulaires)
    voisins = [frozenset(v for v in catalogue if _proche(m, v)) for m in mots]
    # La requête entière, telle quelle : un nom exact, un code « HNB-02 » en
    # cours de frappe. Pas sous quatre lettres : « art » n'est pas « artisanat »
    entiere = normaliser(requete)
    sortie = np.empty(len(fiches))
    for i, (f, vocabulaire) in enumerate(zip(fiches, vocabulaires)):
        if len(entiere) >= 4 and any(entiere in t for t in _textes_entiers(f)):
            sortie[i] = 1.0
        else:
            sortie[i] = sum(not v.isdisjoint(vocabulaire) for v in voisins) / len(mots)
    return sortie


def couverture(f: Fiche, requete: str) -> float:
    return float(couvertures([f], requete)[0])


def correspond(f: Fiche, requete: str) -> bool:
    """Tous les mots utiles de la requête se retrouvent dans la fiche."""
    return couverture(f, requete) == 1.0


# --- Sens ---


def passages(f: Fiche) -> list[str]:
    """Les textes d'une fiche que le modèle compare à la requête."""
    categories = CATEGORIES.get(f.categorie, (f.categorie,) * 3)
    sortie = [
        f"{nom}. {accroche}. {categories[min(i, len(categories) - 1)]}"
        for i, (nom, accroche) in enumerate(f.libelles)
    ]
    nom = f.libelles[0][0]
    sortie += [f"{nom} : {u}" for u in f.usages]
    return sortie


class Index:
    """Vecteurs des fiches, recalculés seulement quand une fiche change."""

    def __init__(self):
        self._cache: dict[Fiche, np.ndarray] = {}
        # Les requêtes se répètent (« lampe », « kitsune ») : les garder évite de
        # repasser par le modèle, le poste le plus lent sur un petit processeur
        self._requetes: dict[tuple[int, str], np.ndarray] = {}
        # Le préchauffage au démarrage et une première requête peuvent se croiser
        self._verrou = threading.Lock()

    def vecteurs(self, encodeur, fiches: list[Fiche]) -> list[np.ndarray]:
        with self._verrou:
            return self._vecteurs(encodeur, fiches)

    def _vecteurs(self, encodeur, fiches: list[Fiche]) -> list[np.ndarray]:
        manquantes = [f for f in fiches if f not in self._cache]
        if manquantes:
            textes = [passages(f) for f in manquantes]
            plats = encodeur.passages([t for bloc in textes for t in bloc])
            debut = 0
            for f, bloc in zip(manquantes, textes):
                self._cache[f] = plats[debut : debut + len(bloc)]
                debut += len(bloc)
            # Les versions périmées d'une fiche modifiée ne s'accumulent pas
            vivantes = set(fiches)
            for f in [f for f in self._cache if f not in vivantes]:
                del self._cache[f]
        return [self._cache[f] for f in fiches]

    def scores(self, encodeur, fiches: list[Fiche], texte: str) -> np.ndarray:
        """Pour chaque fiche, la similarité de son passage le plus proche."""
        q = self._requete(encodeur, texte)
        return np.array([float((v @ q).max()) for v in self.vecteurs(encodeur, fiches)])

    def _requete(self, encodeur, texte: str) -> np.ndarray:
        cle = (id(encodeur), texte)
        vecteur = self._requetes.get(cle)
        if vecteur is None:
            vecteur = encodeur.requetes([texte])[0]
            if len(self._requetes) >= REQUETES_EN_CACHE:
                self._requetes.pop(next(iter(self._requetes)), None)
            self._requetes[cle] = vecteur
        return vecteur


REQUETES_EN_CACHE = 2048


INDEX = Index()


def prechauffer(ouvrir_session) -> None:
    """Charge le modèle et encode le catalogue, hors du chemin des requêtes.

    Lancé au démarrage dans un fil à part : sur un petit processeur, encoder le
    catalogue prend plusieurs secondes, que le premier visiteur n'attend pas.
    """
    try:
        encodeur = plongement.encodeur(attendre=True)
        if encodeur is None:
            return
        with ouvrir_session() as db:
            produits = db.scalars(select(models.Product).where(models.Product.active.is_(True))).all()
            fiches = [fiche(p) for p in produits]
        INDEX.vecteurs(encodeur, fiches)
        log.info("catalogue encodé pour la recherche", extra={"objets": len(fiches)})
    except Exception:
        log.exception("préchauffage de la recherche impossible, elle se fera à la demande")


# --- Assemblage ---


def chercher(fiches: list[Fiche], q: str, encodeur=None) -> list[int]:
    """Identifiants des objets qui répondent à `q`, du plus au moins pertinent."""
    requete = analyser(q)
    dans_le_budget = [
        f for f in fiches
        if (requete.prix_min is None or f.prix_cents >= requete.prix_min)
        and (requete.prix_max is None or f.prix_cents <= requete.prix_max)
    ]
    mots = mots_utiles(requete.texte)
    if not mots or set(mots) <= GENERIQUES:
        # Seul le prix contraint la recherche : du moins cher au plus cher
        if requete.prix_min is None and requete.prix_max is None:
            return []
        return [f.id for f in sorted(dans_le_budget, key=lambda f: f.prix_cents)]

    couv = couvertures(fiches, requete.texte)
    complets = couv == 1.0
    budget = set(dans_le_budget)

    if encodeur is None or len(fiches) < 2:
        return [f.id for f, c in zip(fiches, complets) if c and f in budget]

    # Le sens se juge sur tout le catalogue : un budget serré ne doit pas
    # faire paraître pertinent le moins mauvais des objets restants
    sens = INDEX.scores(encodeur, fiches, requete.texte)
    score = sens - sens.mean() + POIDS_TEXTE * couv
    retenus = complets | (score >= SEUIL)

    choisis = [i for i, f in enumerate(fiches) if retenus[i] and f in budget]
    choisis.sort(key=lambda i: (not complets[i], -score[i]))
    return [fiches[i].id for i in choisis]
