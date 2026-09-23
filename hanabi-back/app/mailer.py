"""Envoi de courriels, selon `MAIL_BACKEND`.

- `fichier` (défaut) : message .eml complet dans `var/courriels/`, sans identifiants ;
- `smtp` : relais réel via `smtplib` ;
- `memoire` : suite de tests.
"""
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from .config import settings

log = logging.getLogger("hanabi.courriel")

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_COURRIELS = RACINE / "var" / "courriels"


@dataclass
class Courriel:
    destinataire: str
    sujet: str
    texte: str
    html: str | None = None
    identifiant: str = field(default_factory=make_msgid)

    def construire(self) -> EmailMessage:
        """Message MIME transmis."""
        msg = EmailMessage()
        msg["Subject"] = self.sujet
        msg["From"] = formataddr((settings.MAIL_FROM_NAME, settings.MAIL_FROM))
        msg["To"] = self.destinataire
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = self.identifiant

        # Texte puis HTML en alternative : un message HTML seul passe souvent en indésirable
        msg.set_content(self.texte)
        if self.html:
            msg.add_alternative(self.html, subtype="html")
        return msg


class ExpediteurMemoire:
    """Garde les messages en mémoire (tests)."""

    def __init__(self):
        self.boite: list[Courriel] = []

    def envoyer(self, courriel: Courriel) -> None:
        self.boite.append(courriel)

    def vider(self) -> None:
        self.boite.clear()


class ExpediteurFichier:
    """Écrit chaque message en .eml dans `var/courriels/`."""

    def envoyer(self, courriel: Courriel) -> None:
        DOSSIER_COURRIELS.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        # Nom de fichier assaini : une adresse malformée n'écrit pas hors du dossier
        sur = "".join(c if c.isalnum() or c in "@.-_" else "_" for c in courriel.destinataire)
        chemin = DOSSIER_COURRIELS / f"{horodatage}-{sur[:60]}.eml"
        chemin.write_bytes(bytes(courriel.construire()))
        log.info("courriel ecrit", extra={"fichier": chemin.name, "sujet": courriel.sujet})


class ExpediteurSMTP:
    """Remet le message à un relais SMTP : 465 en TLS direct, sinon STARTTLS."""

    def envoyer(self, courriel: Courriel) -> None:
        contexte = ssl.create_default_context()
        message = courriel.construire()

        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT, context=contexte
            ) as serveur:
                self._authentifier(serveur)
                serveur.send_message(message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT
            ) as serveur:
                serveur.ehlo()
                if settings.SMTP_STARTTLS:
                    serveur.starttls(context=contexte)
                    # Les capacités changent après TLS
                    serveur.ehlo()
                self._authentifier(serveur)
                serveur.send_message(message)

        log.info(
            "courriel remis au relais",
            extra={"relais": settings.SMTP_HOST, "sujet": courriel.sujet},
        )

    @staticmethod
    def _authentifier(serveur: smtplib.SMTP) -> None:
        # Un relais local peut se passer d'identifiants
        if settings.SMTP_USER:
            serveur.login(settings.SMTP_USER, settings.SMTP_PASSWORD)


def construire_expediteur():
    """Sortie choisie d'après la configuration."""
    mode = settings.MAIL_BACKEND.lower()
    if mode == "memoire":
        return ExpediteurMemoire()
    if mode == "smtp":
        if not settings.SMTP_HOST:
            # Échoue au démarrage plutôt qu'au premier courriel
            raise RuntimeError("MAIL_BACKEND=smtp exige SMTP_HOST.")
        return ExpediteurSMTP()
    return ExpediteurFichier()


# Instance unique, remplaçable par les tests
expediteur = construire_expediteur()


def envoyer(courriel: Courriel) -> None:
    """Remet le message ; les erreurs remontent à la file, qui décide des réessais."""
    expediteur.envoyer(courriel)
