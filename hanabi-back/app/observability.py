"""Journalisation structuree et identifiant de requete.

Ce que ce module change, en une phrase : quand quelque chose casse en
production, on peut repondre a « qu'est-il arrive a CETTE requete-la ».

Avant, les journaux etaient des lignes de texte libre ecrites par uvicorn, sans
rien pour relier entre elles les traces d'un meme appel. Sur un service a une
seule instance et deux visiteurs, cela se lit encore. Des que deux requetes se
chevauchent - et elles se chevauchent toujours - les lignes s'entrelacent et
l'enquete devient de la reconstitution.

Trois pieces, pas une de plus :

1. Un IDENTIFIANT par requete, tire du client s'il en fournit un
   (`X-Request-ID`), sinon genere. Il est renvoye dans la reponse, ce qui permet
   a quelqu'un qui signale un bug de donner la reference exacte de son appel.
2. Un CONTEXTE de tache asynchrone (`contextvars`), pour que tout journal ecrit
   pendant le traitement porte cet identifiant sans qu'on ait a le passer de
   fonction en fonction. Une variable globale ne conviendrait pas : plusieurs
   requetes sont traitees en parallele dans la meme boucle.
3. Un FORMAT JSON en production, lisible en developpement. Les hebergeurs
   indexent le JSON et le rendent interrogeable ; sur un terminal, la meme ligne
   est illisible, donc le format suit l'environnement.
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .config import settings

log = logging.getLogger("hanabi.acces")

# Valeur par defaut explicite : un journal ecrit hors requete (demarrage,
# tache de fond) reste valide et se distingue au lieu de lever.
_id_requete: ContextVar[str] = ContextVar("id_requete", default="-")

EN_TETE = "X-Request-ID"

# Un identifiant fourni par le client est repris tel quel, mais borne : il
# traverse les journaux, et rien n'empeche d'y glisser un roman ou des
# caracteres de controle qui casseraient une ligne JSON.
LONGUEUR_MAX_ID = 64


def id_requete() -> str:
    """Identifiant de la requete en cours de traitement."""
    return _id_requete.get()


class FiltreIdRequete(logging.Filter):
    """Injecte l'identifiant courant dans chaque enregistrement."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.id_requete = id_requete()
        return True


class FormatJSON(logging.Formatter):
    """Une ligne JSON par evenement.

    Les champs supplementaires poses par l'appelant (`extra={...}`) sont
    recopies tels quels : c'est ce qui permet d'ecrire `log.info("commande",
    extra={"numero": ...})` et de retrouver ensuite toutes les commandes par
    une recherche sur un champ, plutot que par une expression reguliere sur du
    texte.
    """

    STANDARDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
        "asctime", "message", "taskName", "id_requete",
    }

    def format(self, record: logging.LogRecord) -> str:
        charge = {
            "horodatage": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "niveau": record.levelname,
            "journal": record.name,
            "message": record.getMessage(),
            "id_requete": getattr(record, "id_requete", "-"),
        }
        for cle, valeur in record.__dict__.items():
            if cle not in self.STANDARDS and not cle.startswith("_"):
                charge[cle] = valeur
        if record.exc_info:
            charge["exception"] = self.formatException(record.exc_info)
        # `default=str` plutot qu'une exception : un journal ne doit jamais
        # faire echouer la requete qu'il decrit.
        return json.dumps(charge, ensure_ascii=False, default=str)


class FormatTexte(logging.Formatter):
    """Meme information, lisible sur un terminal."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        ident = getattr(record, "id_requete", "-")
        return f"{base}  [{ident[:8]}]" if ident != "-" else base


def configurer_journaux() -> None:
    """Installe le format retenu sur la racine, une seule fois."""
    racine = logging.getLogger()
    if any(getattr(h, "_hanabi", False) for h in racine.handlers):
        return

    sortie = logging.StreamHandler(sys.stdout)
    sortie.setFormatter(
        FormatJSON() if settings.LOG_JSON else FormatTexte("%(levelname)s %(name)s: %(message)s")
    )
    sortie.addFilter(FiltreIdRequete())
    sortie._hanabi = True  # marque idempotente : le rechargement a chaud rappelle cette fonction

    # Les gestionnaires deja poses par uvicorn sont retires : sans cela chaque
    # ligne apparaissait deux fois, une par format.
    racine.handlers = [sortie]
    racine.setLevel(settings.LOG_LEVEL.upper())

    # uvicorn tient son propre journal d'acces, redondant avec le notre et non
    # structure. On le tait plutot que de publier deux verites sur la meme
    # requete.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attribue un identifiant, mesure la duree, journalise l'issue."""

    def __init__(self, app: ASGIApp, chemins_silencieux: set[str] | None = None):
        super().__init__(app)
        # `/health` est appele toutes les quelques secondes par la surveillance
        # de l'hebergeur. Le journaliser noierait tout le reste.
        self.silencieux = chemins_silencieux or {"/health", "/healthz"}

    async def dispatch(self, request, call_next):
        entrant = request.headers.get(EN_TETE, "")
        ident = entrant.strip()[:LONGUEUR_MAX_ID] or uuid.uuid4().hex
        jeton = _id_requete.set(ident)

        # `perf_counter` et non `time()` : mesure une duree, insensible aux
        # ajustements d'horloge.
        debut = time.perf_counter()
        try:
            reponse = await call_next(request)
        except Exception:
            duree = (time.perf_counter() - debut) * 1000
            log.exception(
                "requete en echec",
                extra={
                    "methode": request.method,
                    "chemin": request.url.path,
                    "duree_ms": round(duree, 2),
                    "statut": 500,
                },
            )
            _id_requete.reset(jeton)
            raise

        duree = (time.perf_counter() - debut) * 1000
        reponse.headers[EN_TETE] = ident
        # Duree exposee au client : elle permet de distinguer une lenteur
        # serveur d'une lenteur reseau sans avoir acces aux journaux.
        reponse.headers["Server-Timing"] = f"app;dur={duree:.1f}"

        if request.url.path not in self.silencieux:
            log.log(
                logging.WARNING if reponse.status_code >= 500 else logging.INFO,
                "requete",
                extra={
                    "methode": request.method,
                    "chemin": request.url.path,
                    "statut": reponse.status_code,
                    "duree_ms": round(duree, 2),
                    # L'adresse est tronquee a son reseau : suffisant pour
                    # reconnaitre une source abusive, insuffisant pour suivre
                    # une personne. Un journal est une donnee personnelle des
                    # lors qu'il porte une adresse complete.
                    "client": _reseau(request.client.host if request.client else ""),
                },
            )

        _id_requete.reset(jeton)
        return reponse


def _reseau(adresse: str) -> str:
    """Tronque une adresse IP a son prefixe reseau."""
    if ":" in adresse:  # IPv6 : on garde les quatre premiers groupes (/64)
        groupes = adresse.split(":")
        return ":".join(groupes[:4]) + "::/64" if len(groupes) > 4 else adresse
    morceaux = adresse.split(".")
    return ".".join(morceaux[:3]) + ".0/24" if len(morceaux) == 4 else adresse or "-"
