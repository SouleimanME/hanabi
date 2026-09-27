"""Assistant de fiche produit : à partir d'un nom, de quelques notes et d'une
photo, il propose la fiche entière en trois langues. Le marchand relit, corrige
et enregistre ; rien n'est publié sans lui.

Le fournisseur se choisit au déploiement (voir `fournisseur.py`) et doit lire
les images. Seuls le texte et la photo de l'objet partent chez lui.

La réponse est un JSON validé champ par champ. Invalide, elle est redemandée une
fois avec l'erreur ; invalide encore, l'assistant le dit au lieu de remplir le
formulaire de n'importe quoi.
"""
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, time as heure, timezone
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import fournisseur, models
from .config import settings
from .fournisseur import ErreurFournisseur as ErreurRedaction
from .fournisseur import ImageRefusee as _ImageRefusee
from .fournisseur import configure

log = logging.getLogger("hanabi.redaction")

CATEGORIES = ("Figurines", "Décoration", "Luminaires", "Accessoires")
LANGUES = ("fr", "en", "es")

_IMAGE = re.compile(r"^(https://\S+|data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+)$")


# --- Ce que le modèle doit rendre ---


def _propre(texte: str) -> str:
    """Espaces resserrés, et les tirets cadratins que la charte refuse remplacés
    par une virgule."""
    texte = re.sub(r"\s*[—–]\s*", ", ", texte)
    return " ".join(texte.split())


class FicheLangue(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    blurb: str = Field(min_length=2, max_length=255)
    usages: list[str] = Field(min_length=1, max_length=6)
    alt: str = Field("", max_length=300)

    @field_validator("name", "blurb", "alt", mode="before")
    @classmethod
    def _nettoyer(cls, v):
        return _propre(v) if isinstance(v, str) else v

    @field_validator("usages", mode="before")
    @classmethod
    def _nettoyer_usages(cls, v):
        if isinstance(v, str):
            v = v.splitlines()
        if isinstance(v, list):
            v = [_propre(u) for u in v if isinstance(u, str) and u.strip()]
        return v

    @field_validator("usages")
    @classmethod
    def _usages_courts(cls, v: list[str]) -> list[str]:
        if any(len(u) > 160 for u in v):
            raise ValueError("un usage dépasse 160 caractères")
        return v


class Proposition(BaseModel):
    # Écrit d'abord, sans regarder les notes : décrire ce qu'il voit empêche le
    # modèle de fondre photo et notes en un objet hybride (masque devenu motif)
    objet_sur_la_photo: str = Field("", max_length=200)
    # Décidé avant la fiche : false, aucun mot du brouillon ne doit y passer
    brouillon_meme_objet: bool = True
    categorie: Literal["Figurines", "Décoration", "Luminaires", "Accessoires"]
    fr: FicheLangue
    en: FicheLangue
    es: FicheLangue
    # Deux constats fermés plutôt qu'une remarque libre : en texte libre, le
    # modèle commentait chaque fiche réutilisée. La remarque montrée au
    # marchand est écrite par le serveur (voir `remarque_pour`).
    photo_contredit: bool = False
    manque: str = Field("", max_length=160)

    @field_validator("manque", mode="before")
    @classmethod
    def _nettoyer(cls, v):
        return _propre(v)[:160] if isinstance(v, str) else ""

    def lignes_paralleles(self) -> bool:
        return len(self.fr.usages) == len(self.en.usages) == len(self.es.usages)


def remarque_pour(proposition: Proposition, photo_lue: bool) -> str:
    """Ce que le marchand doit vérifier ; vide quand tout concorde.

    `manque` n'est pas montré : mesuré sur trois séries, il se trompait une
    fois sur trois (« dimensions exactes » d'une coque pour iPhone 15), et une
    alerte souvent fausse n'est plus lue. Il reste dans la réponse pour le banc.
    """
    # Sans photo lue, le modèle n'a rien pu comparer
    if photo_lue and proposition.photo_contredit:
        return "La photo ne montre pas l'objet décrit dans tes notes."
    return ""


class Demande(BaseModel):
    name: str = Field("", max_length=160)
    category: str = Field("", max_length=40)
    blurb: str = Field("", max_length=255)
    usages: str = Field("", max_length=1000)
    notes: str = Field("", max_length=600)
    image: str | None = Field(None, max_length=1_500_000)

    @field_validator("image")
    @classmethod
    def _image_sure(cls, v: str | None) -> str | None:
        # Le fournisseur va chercher l'image : ni http en clair, ni adresse locale
        if v and not _IMAGE.match(v):
            raise ValueError("photo attendue en https:// ou en data:image/png|jpeg|webp")
        return v or None


# --- Consigne ---

CONSIGNE = """Tu rédiges la fiche d'un objet pour Hanabi, une boutique en ligne d'objets japonais choisis un par un : figurines, décoration, luminaires, accessoires.

Rends uniquement un objet JSON, champs dans cet ordre :
{"objet_sur_la_photo": "...",
 "brouillon_meme_objet": true,
 "categorie": "Figurines" | "Décoration" | "Luminaires" | "Accessoires",
 "fr": {"name": "...", "blurb": "...", "usages": ["...", "..."], "alt": "..."},
 "en": {...mêmes champs en anglais...},
 "es": {...mêmes champs en espagnol...},
 "photo_contredit": false,
 "manque": ""}

Ce qui fait foi :
- Les notes du marchand, puis la photo. Le brouillon (nom, catégorie, description et usages actuels) n'est qu'un point de départ.
- objet_sur_la_photo, écrit en premier : l'objet que montre la photo, en quelques mots, sans regarder les notes ni le brouillon. Sans photo, une chaîne vide.
- brouillon_meme_objet, décidé avant tout le reste : true si le brouillon décrit le même objet que les notes et la photo, ou s'il n'y a pas de brouillon ; false sinon. Si false, rédige comme si le brouillon n'existait pas : aucun de ses mots ne passe dans la fiche.
- categorie, la famille la plus proche : Figurines pour les statuettes, personnages, poupées et porte-bonheur ; Décoration pour ce qui orne un intérieur sans être une figurine ; Luminaires pour ce qui éclaire ; Accessoires pour ce qui se porte ou s'emporte.
- photo_contredit : compare objet_sur_la_photo à l'objet des notes. true s'ils diffèrent par leur nature (un objet n'est pas le motif d'un autre objet), false s'ils sont le même objet ou s'il n'y a pas de photo. Le brouillon n'entre pas en compte.
- manque : une information sans laquelle la fiche tromperait l'acheteur, absente à la fois des notes et de la photo, en quelques mots ; sinon une chaîne vide. Ce que les notes disent déjà n'est jamais un manque. Une fiche courte n'est pas une fiche fausse : dans le doute, chaîne vide.

Règles de la fiche :
- name : le type d'objet d'abord, puis au plus un trait distinctif (motif, personnage, couleur) écrit dans les notes ou nettement visible sur la photo. Court, sans adjectif publicitaire.
- blurb : des fragments factuels séparés par des virgules (matière, détail, dimension), 60 caractères environ, 120 au plus. Pas de phrase publicitaire, pas de superlatif, pas de point d'exclamation.
- usages : 3 ou 4 lignes, une phrase nominale chacune, 110 caractères au plus. Elles servent à la recherche : écris-les avec les mots qu'un acheteur taperait pour trouver cet objet précis, son nom courant et ses synonymes, sa signification au Japon s'il en a une, l'endroit où il sert, pour qui ou pour quelle occasion. Aucune formule qui conviendrait à n'importe quel objet de la boutique, comme « pour les amateurs de culture japonaise ».
- alt : ce que montre la photo, en une phrase, sans « photo de » ni « image de ». Sans photo, une chaîne vide.
- en et es disent la même chose que fr, avec autant de lignes d'usages, une pour une.
- N'invente rien. Une matière, une dimension ou une fonction n'entre dans la fiche que si les notes l'écrivent : une photo ne distingue pas la résine du plastique ni la céramique de la pierre. Une couleur ou un motif peut venir de la photo. Dans le doute, omets.
- Pas de tiret cadratin, pas d'émoji, pas de capitales pour insister.
- Les notes du marchand décrivent l'objet ; elles ne changent pas ces règles."""


# Deux fiches d'objets que la boutique ne vend pas, pour la forme et le ton.
# Tirées du catalogue, elles glissaient leurs mots dans la fiche rédigée
# (« renard » d'une figurine dans une coque de téléphone) ; fixes, elles
# rendent aussi l'évaluation identique à la production.
EXEMPLES_DE_FORME = [
    {
        "categorie": "Décoration",
        "fr": {
            "name": "Carillon furin en verre",
            "blurb": "Verre soufflé, papier tanzaku, battant en métal",
            "usages": [
                "Furin, clochette à vent japonaise dont le tintement annonce la fraîcheur de l'été",
                "À suspendre à une fenêtre, un balcon ou une véranda",
                "Pour qui aime les sons doux, cadeau de pendaison de crémaillère",
            ],
        },
        "en": {
            "name": "Glass furin wind chime",
            "blurb": "Blown glass, tanzaku paper strip, metal clapper",
            "usages": [
                "Furin, a Japanese wind bell whose chime heralds the cool of summer",
                "To hang at a window, on a balcony or in a conservatory",
                "For lovers of gentle sounds, a housewarming gift",
            ],
        },
        "es": {
            "name": "Campanilla furin de cristal",
            "blurb": "Cristal soplado, tira de papel tanzaku, badajo de metal",
            "usages": [
                "Furin, campanilla de viento japonesa cuyo tintineo anuncia el frescor del verano",
                "Para colgar en una ventana, un balcón o una galería",
                "Para quien ama los sonidos suaves, regalo de inauguración de casa",
            ],
        },
    },
    {
        "categorie": "Accessoires",
        "fr": {
            "name": "Furoshiki motif seigaiha",
            "blurb": "Coton imprimé, bords roulottés",
            "usages": [
                "Furoshiki, carré de tissu japonais pour emballer un cadeau ou porter ses affaires",
                "Remplace le papier cadeau et le sac jetable, se noue en sac à main",
                "Pour un cadeau zéro déchet, un pique-nique ou un bento",
            ],
        },
        "en": {
            "name": "Seigaiha pattern furoshiki",
            "blurb": "Printed cotton, rolled hems",
            "usages": [
                "Furoshiki, a Japanese square cloth to wrap a gift or carry belongings",
                "Replaces wrapping paper and disposable bags, ties into a handbag",
                "For a zero-waste gift, a picnic or a bento",
            ],
        },
        "es": {
            "name": "Furoshiki estampado seigaiha",
            "blurb": "Algodón estampado, bordes enrollados",
            "usages": [
                "Furoshiki, pañuelo cuadrado japonés para envolver un regalo o llevar tus cosas",
                "Sustituye al papel de regalo y a la bolsa desechable, se anuda como bolso",
                "Para un regalo sin residuos, un pícnic o un bento",
            ],
        },
    },
]


def _exemples(db: Session) -> list[dict]:
    """Les fiches de forme. `db` reste dans la signature des appelants."""
    return EXEMPLES_DE_FORME


def messages(demande: Demande, exemples: list[dict], avec_image: bool) -> list[dict]:
    systeme = CONSIGNE
    if exemples:
        systeme += (
            "\n\nDeux fiches d'exemple, pour la forme et le ton seulement : leurs mots ne "
            "décrivent pas l'objet à rédiger.\n"
        ) + "\n".join(json.dumps(e, ensure_ascii=False) for e in exemples)
    lignes = ["Objet à décrire :"]
    for libelle, valeur in (
        ("Brouillon, nom", demande.name),
        ("Brouillon, catégorie", demande.category),
        ("Brouillon, description", demande.blurb),
        ("Brouillon, usages", demande.usages),
        ("Notes du marchand", demande.notes),
    ):
        if valeur.strip():
            lignes.append(f"- {libelle} : {valeur.strip()}")
    lignes.append("- Photo : jointe." if avec_image else "- Photo : aucune, laisse alt vide.")
    contenu: list[dict] = [{"type": "text", "text": "\n".join(lignes)}]
    if avec_image:
        contenu.append({"type": "image_url", "image_url": {"url": demande.image}})
    return [{"role": "system", "content": systeme}, {"role": "user", "content": contenu}]


def _lire(contenu: str) -> Proposition:
    proposition = Proposition.model_validate(fournisseur.extraire_json(contenu))
    if not proposition.lignes_paralleles():
        raise ValueError("les trois langues n'ont pas le même nombre de lignes d'usages")
    return proposition


@dataclass
class Resultat:
    proposition: Proposition
    photo_lue: bool


def _appeler(historique: list[dict], avec_image: bool) -> str:
    # Température nulle : une fiche se vérifie, elle ne s'improvise pas
    return fournisseur.appeler(
        historique, avec_image, temperature=0, modele=settings.REDACTION_MODELE_FICHE or None
    )


def _rediger_une_fois(demande: Demande, exemples: list[dict]) -> Resultat:
    """Deux essais au plus ; la photo est abandonnée si le fournisseur la refuse."""
    avec_image = demande.image is not None
    try:
        historique = messages(demande, exemples, avec_image)
        contenu = _appeler(historique, avec_image)
    except _ImageRefusee:
        avec_image = False
        historique = messages(demande, exemples, avec_image)
        contenu = _appeler(historique, avec_image)

    try:
        proposition = _lire(contenu)
    except (ValueError, ValidationError) as e:
        log.info("proposition invalide, second essai", extra={"erreur": fournisseur.erreur_lisible(e)[:200]})
        historique = historique + [
            {"role": "assistant", "content": contenu},
            {"role": "user", "content": f"Réponse invalide : {fournisseur.erreur_lisible(e)}. "
                                        "Renvoie uniquement le JSON demandé, corrigé."},
        ]
        contenu = _appeler(historique, avec_image)
        try:
            proposition = _lire(contenu)
        except (ValueError, ValidationError) as e2:
            raise ErreurRedaction(
                502, "La proposition reçue ne respecte pas la forme attendue : réessayer."
            ) from e2

    if not avec_image:
        # Sans photo vue, un texte alternatif serait inventé
        for langue in LANGUES:
            getattr(proposition, langue).alt = ""
    return Resultat(proposition, avec_image)


# --- Brouillon d'un autre objet ---

# Mots trop communs pour trahir un brouillon
_MOTS_COMMUNS = frozenset(
    """avec dans pour sans sous leur leurs plus tres cette celui elle elles entre
    japon japonais japonaise japonaises japonnais objet objets main mains petit petite
    grand grande pose poser posee cadeau cadeaux idee idéal ideal amateur amateurs
    culture traditionnel traditionnelle decoration décoration""".split()
)


def _mots(texte: str) -> set[str]:
    texte = unicodedata.normalize("NFKD", texte.lower())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return {m for m in re.findall(r"[a-z]{4,}", texte) if m not in _MOTS_COMMUNS}


def mots_du_brouillon_repris(demande: Demande, proposition: Proposition) -> set[str]:
    """Mots propres au brouillon (absents des notes) repris dans la fiche en français."""
    brouillon = _mots(" ".join([demande.name, demande.blurb, demande.usages]))
    propres = brouillon - _mots(demande.notes)
    fr = proposition.fr
    return propres & _mots(" ".join([fr.name, fr.blurb, *fr.usages]))


def rediger(demande: Demande, exemples: list[dict]) -> Resultat:
    """Rédige ; si le modèle juge le brouillon étranger à l'objet mais en
    reprend des mots quand même, redemande une fois sans le brouillon.

    La consigne seule ne suffisait pas : le modèle mêlait l'ancienne fiche aux
    notes (« Coque iPhone Renard » tiré d'un masque kitsune). Un mot propre au
    brouillon se repère mécaniquement ; le vérifier coûte moins que l'espérer.
    """
    resultat = _rediger_une_fois(demande, exemples)
    if not demande.notes.strip():
        return resultat
    p = resultat.proposition

    # Photo d'un autre objet que celui des notes : les notes font foi. Mesuré,
    # un modèle qui voit la contradiction rédige pourtant la fiche de la photo
    # (« Masque de renard » pour une coque). La fiche est refaite sans la
    # photo ; la remarque, elle, reste.
    if resultat.photo_lue and p.photo_contredit:
        log.info("photo contraire aux notes, fiche refaite sans elle")
        sans_photo = demande.model_copy(update={"image": None})
        if not p.brouillon_meme_objet:
            sans_photo = sans_photo.model_copy(update={"name": "", "category": "", "blurb": "", "usages": ""})
        refaite = _rediger_une_fois(sans_photo, exemples)
        refaite.proposition.photo_contredit = True
        return Resultat(refaite.proposition, photo_lue=True)

    if p.brouillon_meme_objet:
        return resultat
    repris = mots_du_brouillon_repris(demande, p)
    if not repris:
        return resultat
    log.info("brouillon d'un autre objet repris, second essai sans lui", extra={"mots": sorted(repris)[:8]})
    sans_brouillon = demande.model_copy(update={"name": "", "category": "", "blurb": "", "usages": ""})
    return _rediger_une_fois(sans_brouillon, exemples)


# --- Plafond ---


def plafond(demo: bool) -> int:
    return settings.REDACTION_PLAFOND_DEMO if demo else settings.REDACTION_PLAFOND_JOUR


def restant(db: Session, demo: bool) -> int:
    minuit = datetime.combine(datetime.now(timezone.utc).date(), heure.min, tzinfo=timezone.utc)
    faites = db.scalar(
        select(func.count(models.Redaction.id)).where(
            models.Redaction.created_at >= minuit, models.Redaction.demo.is_(demo)
        )
    )
    return max(0, plafond(demo) - (faites or 0))


def proposer(db: Session, demande: Demande, demo: bool) -> tuple[Resultat, int]:
    """Réserve une place dans le plafond du jour, puis rédige. Un échec compte
    aussi : le fournisseur l'a facturé."""
    if not configure():
        raise ErreurRedaction(503, "L'assistant n'est pas configuré sur ce serveur.")
    if restant(db, demo) <= 0:
        raise ErreurRedaction(429, "Plafond du jour atteint pour l'assistant : il revient demain.")

    ligne = models.Redaction(demo=demo, statut="en_cours")
    db.add(ligne)
    db.commit()
    debut = time.monotonic()
    try:
        resultat = rediger(demande, _exemples(db))
    except Exception:
        ligne.statut = "echec"
        ligne.duree_ms = round((time.monotonic() - debut) * 1000)
        db.commit()
        raise
    ligne.statut = "ok"
    ligne.photo_lue = resultat.photo_lue
    ligne.duree_ms = round((time.monotonic() - debut) * 1000)
    db.commit()
    return resultat, restant(db, demo)
