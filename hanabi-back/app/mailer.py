"""Envoi de courriels.

TROIS SORTIES POUR UN SEUL APPELANT. Le reste du code ecrit `envoyer(courriel)`
et ignore ou cela part ; c'est la configuration qui tranche :

  - `fichier` (defaut) : chaque message est ecrit dans `var/courriels/` au
    format .eml, ouvrable d'un double-clic dans n'importe quel client. Aucune
    configuration, aucun identifiant, rien ne quitte la machine. C'est ce qui
    permet a quiconque clone le depot de voir les courriels de la boutique sans
    creer de compte nulle part.
  - `smtp` : un vrai relais. `smtplib` suffit - aucune dependance ajoutee.
  - `memoire` : la suite de tests, qui inspecte ce qui a ete produit sans
    toucher au disque.

Pourquoi pas SMTP par defaut : un depot qui exige des identifiants pour demarrer
n'est pas clonable. Le mode fichier est un vrai mode de fonctionnement, pas un
bouchon - il produit le message complet, en-tetes compris, et c'est le meme
objet qui partirait sur le reseau.

RELAIS GRATUITS, pour memoire : Brevo offre 300 messages par jour a vie, Resend
3 000 par mois, et Gmail accepte 500 par jour avec un mot de passe
d'application. Tous parlent le SMTP standard, donc tous fonctionnent ici sans
une ligne de code supplementaire.
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
    # Renseigne a l'envoi : sert a relier le message a la trace du journal.
    identifiant: str = field(default_factory=make_msgid)

    def construire(self) -> EmailMessage:
        """Assemble le message MIME reellement transmis."""
        msg = EmailMessage()
        msg["Subject"] = self.sujet
        msg["From"] = formataddr((settings.MAIL_FROM_NAME, settings.MAIL_FROM))
        msg["To"] = self.destinataire
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = self.identifiant

        # Version texte d'abord, HTML en alternative : c'est l'ordre impose par
        # MIME, le client retenant la derniere partie qu'il sait afficher. Un
        # message HTML sans equivalent texte part au courrier indesirable chez
        # une bonne partie des filtres.
        msg.set_content(self.texte)
        if self.html:
            msg.add_alternative(self.html, subtype="html")
        return msg


class ExpediteurMemoire:
    """Conserve les messages en memoire. Utilise par la suite de tests."""

    def __init__(self):
        self.boite: list[Courriel] = []

    def envoyer(self, courriel: Courriel) -> None:
        self.boite.append(courriel)

    def vider(self) -> None:
        self.boite.clear()


class ExpediteurFichier:
    """Ecrit chaque message dans `var/courriels/`, au format .eml."""

    def envoyer(self, courriel: Courriel) -> None:
        DOSSIER_COURRIELS.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        # L'adresse entre dans le nom de fichier : on ne garde que des
        # caracteres surs, sans quoi un destinataire malforme ecrirait hors du
        # dossier prevu.
        sur = "".join(c if c.isalnum() or c in "@.-_" else "_" for c in courriel.destinataire)
        chemin = DOSSIER_COURRIELS / f"{horodatage}-{sur[:60]}.eml"
        chemin.write_bytes(bytes(courriel.construire()))
        log.info("courriel ecrit", extra={"fichier": chemin.name, "sujet": courriel.sujet})


class ExpediteurSMTP:
    """Remet le message a un relais SMTP.

    Deux facons de chiffrer, et les confondre est l'erreur la plus courante :
      - port 465, la session est chiffree des l'ouverture (SMTPS / `SMTP_SSL`) ;
      - port 587, la session s'ouvre en clair puis passe en TLS (`STARTTLS`).
    Un port 587 aborde en SMTPS reste bloque jusqu'au delai d'attente, sans
    message d'erreur utile. Le choix se deduit donc du port.
    """

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
                    # Second `ehlo` obligatoire : les capacites annoncees avant
                    # le passage en TLS ne valent plus apres, et l'authentification
                    # n'est souvent proposee qu'ensuite.
                    serveur.ehlo()
                self._authentifier(serveur)
                serveur.send_message(message)

        log.info(
            "courriel remis au relais",
            extra={"relais": settings.SMTP_HOST, "sujet": courriel.sujet},
        )

    @staticmethod
    def _authentifier(serveur: smtplib.SMTP) -> None:
        # Un relais local de developpement n'exige pas d'identifiants.
        if settings.SMTP_USER:
            serveur.login(settings.SMTP_USER, settings.SMTP_PASSWORD)


def construire_expediteur():
    """Choisit la sortie d'apres la configuration."""
    mode = settings.MAIL_BACKEND.lower()
    if mode == "memoire":
        return ExpediteurMemoire()
    if mode == "smtp":
        if not settings.SMTP_HOST:
            # Echouer au demarrage plutot qu'au premier courriel : une commande
            # passee est un mauvais moment pour decouvrir que le relais n'est
            # pas configure.
            raise RuntimeError("MAIL_BACKEND=smtp exige SMTP_HOST.")
        return ExpediteurSMTP()
    return ExpediteurFichier()


# Instance unique, remplacable par les tests.
expediteur = construire_expediteur()


def envoyer(courriel: Courriel) -> None:
    """Remet le message a la sortie configuree.

    Les erreurs ne sont pas absorbees ici : c'est la file d'attente
    (`app/outbox.py`) qui decide de reessayer, parce qu'elle seule sait combien
    de tentatives ont deja eu lieu.
    """
    expediteur.envoyer(courriel)
