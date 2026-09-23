"""Défenses anti-robots sans service tiers.

Un CAPTCHA du marché transmettrait IP et comportement à un tiers, contre la
politique cookies du site, et resterait peu accessible. Trois barrières :

1. pot de miel : champ invisible que remplissent les robots ;
2. délai minimal : horodatage signé, un envoi trop rapide est refusé ;
3. preuve de travail : trouver un `nonce` tel que sha256(salt + nonce) commence
   par N bits à zéro.

Défis signés par HMAC, non stockés ; seuls les défis consommés sont mémorisés,
en mémoire du processus (Redis serait nécessaire à plusieurs instances).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from .config import settings

# Défis consommés : sel -> expiration. Purge à chaque vérification.
_used: dict[str, float] = {}
_MAX_USED = 10_000


def _purge(now: float) -> None:
    if len(_used) < _MAX_USED:
        expired = [salt for salt, exp in _used.items() if exp < now]
    else:
        # Cache saturé : vidé entièrement
        expired = list(_used)
    for salt in expired:
        _used.pop(salt, None)


def _sign(salt: str, issued_at: float, purpose: str) -> str:
    msg = f"{salt}|{issued_at}|{purpose}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


class Challenge(BaseModel):
    """Défi remis au client. `min_seconds` et `ttl_seconds` évitent de dupliquer la politique côté front."""

    salt: str
    difficulty: int
    issued_at: float
    purpose: str
    signature: str
    min_seconds: float
    ttl_seconds: int


class AntiBotFields(BaseModel):
    """Champs joints à chaque formulaire public ; `honeypot` doit rester vide."""

    salt: str = Field(max_length=64)
    issued_at: float
    signature: str = Field(max_length=128)
    nonce: str = Field(max_length=64)
    honeypot: str = Field("", max_length=200)


def issue_challenge(purpose: str) -> Challenge:
    """Défi signé pour un usage (`register`, `notify`...)."""
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
        bits += 8 - byte.bit_length()
        break
    return bits


def verify(fields: AntiBotFields, purpose: str) -> None:
    """Valide les barrières ou lève un 400, avec un message unique qui ne dit pas laquelle a échoué."""
    now = time.time()
    generic = "Vérification anti-robot échouée. Recharge la page et réessaie."

    # Pot de miel
    if fields.honeypot.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    # Signature, comparée à temps constant
    expected = _sign(fields.salt, fields.issued_at, purpose)
    if not hmac.compare_digest(expected, fields.signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    # Validité et délai minimal de saisie
    age = now - fields.issued_at
    if age > settings.POW_TTL_SECONDS or age < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)
    if age < settings.MIN_FORM_SECONDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    # Un défi ne sert qu'une fois
    _purge(now)
    if fields.salt in _used:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    # Preuve de travail
    digest = hashlib.sha256(f"{fields.salt}{fields.nonce}".encode()).digest()
    if _leading_zero_bits(digest) < settings.POW_DIFFICULTY:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, generic)

    _used[fields.salt] = fields.issued_at + settings.POW_TTL_SECONDS


# --- Échecs d'authentification ---
# Comptés par e-mail en plus de l'IP (bourrage d'identifiants réparti).
# En mémoire du processus, comme le cache ci-dessus.

FAILURE_WINDOW_SECONDS = 900  # 15 minutes
MAX_FAILURES = 8

_failures: dict[str, list[float]] = {}


def record_failure(key: str) -> None:
    """Enregistre un échec pour cette clé (e-mail ou IP)."""
    now = time.time()
    attempts = [t for t in _failures.get(key, []) if now - t < FAILURE_WINDOW_SECONDS]
    attempts.append(now)
    _failures[key] = attempts


def clear_failures(key: str) -> None:
    """Remet le compteur à zéro après une authentification réussie."""
    _failures.pop(key, None)


def check_throttle(key: str) -> None:
    """429 avec `Retry-After` pour une clé qui accumule les échecs."""
    now = time.time()
    attempts = [t for t in _failures.get(key, []) if now - t < FAILURE_WINDOW_SECONDS]
    _failures[key] = attempts
    if len(attempts) >= MAX_FAILURES:
        retry_after = int(FAILURE_WINDOW_SECONDS - (now - attempts[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Trop de tentatives. Réessaie dans quelques minutes.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
