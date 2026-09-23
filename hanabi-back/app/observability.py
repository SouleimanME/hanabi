"""Journalisation structurée et identifiant de requête.

- Un identifiant par requête (`X-Request-ID` repris du client ou généré),
  renvoyé dans la réponse.
- Porté par `contextvars` : tout journal écrit pendant la requête le reprend.
- JSON en production, texte lisible en développement.
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

# "-" hors requête (démarrage, tâche de fond)
_id_requete: ContextVar[str] = ContextVar("id_requete", default="-")

EN_TETE = "X-Request-ID"

# Identifiant client borné : il traverse les journaux
LONGUEUR_MAX_ID = 64


def id_requete() -> str:
    """Identifiant de la requête en cours."""
    return _id_requete.get()


class FiltreIdRequete(logging.Filter):
    """Ajoute l'identifiant courant à chaque enregistrement."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.id_requete = id_requete()
        return True


class FormatJSON(logging.Formatter):
    """Une ligne JSON par événement, champs `extra` compris."""

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
        # `default=str` : un journal ne fait jamais échouer la requête
        return json.dumps(charge, ensure_ascii=False, default=str)


class FormatTexte(logging.Formatter):
    """Même information, pour un terminal."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        ident = getattr(record, "id_requete", "-")
        return f"{base}  [{ident[:8]}]" if ident != "-" else base


def configurer_journaux() -> None:
    """Installe le format sur la racine, une seule fois."""
    racine = logging.getLogger()
    if any(getattr(h, "_hanabi", False) for h in racine.handlers):
        return

    sortie = logging.StreamHandler(sys.stdout)
    sortie.setFormatter(
        FormatJSON() if settings.LOG_JSON else FormatTexte("%(levelname)s %(name)s: %(message)s")
    )
    sortie.addFilter(FiltreIdRequete())
    sortie._hanabi = True  # le rechargement à chaud rappelle cette fonction

    # Remplace les gestionnaires d'uvicorn (sinon chaque ligne sort deux fois)
    racine.handlers = [sortie]
    racine.setLevel(settings.LOG_LEVEL.upper())

    # Journal d'accès d'uvicorn redondant avec celui-ci
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attribue un identifiant, mesure la durée, journalise l'issue."""

    def __init__(self, app: ASGIApp, chemins_silencieux: set[str] | None = None):
        super().__init__(app)
        # Sondes appelées en continu
        self.silencieux = chemins_silencieux or {"/health", "/healthz"}

    async def dispatch(self, request, call_next):
        entrant = request.headers.get(EN_TETE, "")
        ident = entrant.strip()[:LONGUEUR_MAX_ID] or uuid.uuid4().hex
        jeton = _id_requete.set(ident)

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
        # Distingue lenteur serveur et lenteur réseau côté client
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
                    # Adresse tronquée à son réseau
                    "client": _reseau(request.client.host if request.client else ""),
                },
            )

        _id_requete.reset(jeton)
        return reponse


def _reseau(adresse: str) -> str:
    """Tronque une adresse IP à son préfixe (/24 en IPv4, /64 en IPv6)."""
    if ":" in adresse:
        groupes = adresse.split(":")
        return ":".join(groupes[:4]) + "::/64" if len(groupes) > 4 else adresse
    morceaux = adresse.split(".")
    return ".".join(morceaux[:3]) + ".0/24" if len(morceaux) == 4 else adresse or "-"
