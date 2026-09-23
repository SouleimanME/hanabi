"""Lien de désinscription de la lettre d'information.

Chaque lettre porte un lien signé (HMAC du numéro d'inscription) : un clic
suffit, sans compte ni mot de passe, et personne ne peut désinscrire une
adresse dont il n'a pas reçu le courriel. Le lien ne contient pas l'adresse :
elle finirait dans l'historique du navigateur et les journaux de l'hébergeur.

Changer `SECRET_KEY` invalide les liens déjà envoyés ; la page de
désinscription propose alors d'écrire.
"""
import hashlib
import hmac
from urllib.parse import urlencode

from .config import settings

_USAGE = b"desinscription-lettre"


def signature(identifiant: int) -> str:
    """Signature du numéro d'inscription."""
    message = _USAGE + b"|" + str(int(identifiant)).encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def signature_valide(identifiant: int, recue: str) -> bool:
    """Comparaison à temps constant."""
    return hmac.compare_digest(signature(identifiant), recue)


def lien(identifiant: int) -> str:
    """Adresse de la page de désinscription de la boutique, pour cette inscription."""
    requete = urlencode({"i": int(identifiant), "s": signature(identifiant)})
    return f"{settings.PUBLIC_SITE_URL.rstrip('/')}/desinscription?{requete}"
