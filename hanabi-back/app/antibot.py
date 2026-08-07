"""
Defenses anti-robots, sans service tiers.

Pourquoi pas un CAPTCHA du marche : reCAPTCHA et consorts envoient l'adresse IP
et le comportement de navigation du visiteur a un tiers, ce qui demande une base
legale et un consentement sous RGPD. La politique cookies du site annonce
qu'aucun traceur tiers n'est depose ; ces briques tiennent cette promesse. Elles
sont aussi accessibles, contrairement a un CAPTCHA visuel.

Trois barrieres qui se completent, du moins couteux au plus couteux :

  1. Pot de miel - un champ invisible pour l'humain, rempli par les robots qui
     completent aveuglement tout formulaire. Cout nul, attrape les robots
     basiques, tres nombreux.

  2. Delai minimal - un formulaire renvoye en moins de MIN_FORM_SECONDS n'a pas
     ete saisi par une personne. L'horodatage est signe par le serveur, donc
     l'attaquant ne peut pas l'antidater.

  3. Preuve de travail - le client doit trouver un `nonce` tel que
     sha256(salt + nonce) commence par N bits a zero. Imperceptible pour une
     personne (quelques centaines de millisecondes, une fois), mais rend une
     campagne de spam de masse economiquement penible.

Les defis sont signes par HMAC et non stockes : le serveur n'a rien a garder
pour verifier qu'un defi vient bien de lui. Seuls les defis deja consommes sont
memorises, afin d'empecher la rejouabilite.

Limite connue : ce cache de rejouabilite vit dans le processus. Derriere
plusieurs instances, un meme defi pourrait servir une fois par instance ; il
faudrait alors le deplacer dans Redis. La signature et l'expiration, elles,
restent valides quel que soit le nombre d'instances.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from .config import settings

# --- Defis deja utilises : sel -> instant d'expiration ---
# Purge opportuniste a chaque insertion, ce qui evite une tache de fond.
_used: dict[str, float] = {}
_MAX_USED = 10_000


def _purge(now: float) -> None:
    if len(_used) < _MAX_USED:
        expired = [salt for salt, exp in _used.items() if exp < now]
    else:
        # Cache sature : on vide agressivement plutot que de grossir sans fin.
        expired = list(_used)
    for salt in expired:
        _used.pop(salt, None)


def _sign(salt: str, issued_at: float, purpose: str) -> str:
    msg = f"{salt}|{issued_at}|{purpose}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


class Challenge(BaseModel):
    """Defi remis au client, a resoudre avant l'envoi d'un formulaire.

    `min_seconds` et `ttl_seconds` sont transmis pour que le client n'ait pas a
    dupliquer la politique du serveur. Sans cela, une personne qui valide tres
    vite - remplissage automatique du navigateur puis clic immediat - se ferait
    refuser a tort, et corriger le delai cote serveur demanderait de penser a
    modifier aussi le front.
    """

    salt: str
    difficulty: int
    issued_at: float
    purpose: str
    signature: str
    min_seconds: float
    ttl_seconds: int


class AntiBotFields(BaseModel):
    """Champs anti-robots joints a chaque formulaire public.

    `honeypot` doit rester vide : le formulaire le rend invisible et hors du
    parcours de tabulation, donc une personne ne peut pas le remplir.
    """

    salt: str = Field(max_length=64)
    issued_at: float
    signature: str = Field(max_length=128)
    nonce: str = Field(max_length=64)
    honeypot: str = Field("", max_length=200)


def issue_challenge(purpose: str) -> Challenge:
    """Fabrique un defi signe pour un usage donne (`register`, `notify`...)."""
    salt = secrets.token_hex(16)
    issued_at = time.time()
    return Challenge(
        salt=salt,
        difficulty=settings.POW_DIFFICULTY,
        issued_at=issued_at,
        purpose=purpose,
        signature=_sign(salt, issued_at, purpose),
        min_seconds=settings.MIN_FORM_SECONDS,
        ttl_seconds=settings.POW_TTL_SECONDS,
    )


def _leading_zero_bits(digest: bytes) -> int:
    bits = 0
    for byte in digest:
        if byte == 0:
            bits += 8
            continue
        # 8 moins la position du bit de poids fort mis a 1.
        bits += 8 - byte.bit_length()
        break
    return bits


def verify(fields: AntiBotFields, purpose: str) -> None:
    """Valide les trois barrieres, ou leve une erreur HTTP 400.

    Les messages restent volontairement laconiques : detailler laquelle des
    barrieres a saute aiderait un attaquant a la contourner une par une.
    """
    now = time.time()
    generic = "Verification anti-robot echouee. Recharge la page et reessaie."

    # 1. Pot de miel : rempli => robot.
    if fields.honeypot.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    # 2. Signature : le defi vient-il bien de nous ?
    #    hmac.compare_digest : comparaison a temps constant, pour ne pas laisser
    #    fuir la signature attendue via le temps de reponse.
    expected = _sign(fields.salt, fields.issued_at, purpose)
    if not hmac.compare_digest(expected, fields.signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    # 3. Fenetre de validite, et delai minimal de saisie.
    age = now - fields.issued_at
    if age > settings.POW_TTL_SECONDS or age < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)
    if age < settings.MIN_FORM_SECONDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    # 4. Rejouabilite : un defi ne sert qu'une fois.
    _purge(now)
    if fields.salt in _used:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    # 5. Preuve de travail.
    digest = hashlib.sha256(f"{fields.salt}{fields.nonce}".encode()).digest()
    if _leading_zero_bits(digest) < settings.POW_DIFFICULTY:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    _used[fields.salt] = fields.issued_at + settings.POW_TTL_SECONDS


# --- Limitation des echecs d'authentification ---
#
# Le rate limiting de slowapi est indexe sur l'IP. Il ne freine donc pas un
# bourrage d'identifiants distribue sur des milliers d'adresses, qui ne fait que
# quelques essais par IP mais des milliers sur un meme compte. On compte donc
# aussi les echecs par e-mail vise.
#
# Meme limite que le cache de rejouabilite : en memoire, donc par processus.

FAILURE_WINDOW_SECONDS = 900  # 15 minutes
MAX_FAILURES = 8

_failures: dict[str, list[float]] = {}


def record_failure(key: str) -> None:
    """Enregistre un echec d'authentification pour cette cle (e-mail ou IP)."""
    now = time.time()
    attempts = [t for t in _failures.get(key, []) if now - t < FAILURE_WINDOW_SECONDS]
    attempts.append(now)
    _failures[key] = attempts


def clear_failures(key: str) -> None:
    """Remet le compteur a zero apres une authentification reussie."""
    _failures.pop(key, None)


def check_throttle(key: str) -> None:
    """Bloque temporairement une cle qui accumule les echecs.

    Renvoie 429 avec `Retry-After`, afin qu'un client legitime sache quand
    revenir plutot que de marteler l'API.
    """
    now = time.time()
    attempts = [t for t in _failures.get(key, []) if now - t < FAILURE_WINDOW_SECONDS]
    _failures[key] = attempts
    if len(attempts) >= MAX_FAILURES:
        retry_after = int(FAILURE_WINDOW_SECONDS - (now - attempts[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Trop de tentatives. Reessaie dans quelques minutes.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
