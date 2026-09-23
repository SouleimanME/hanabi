"""Politique de mot de passe, appliquée côté serveur (la jauge du navigateur n'est qu'une aide).

NIST SP 800-63B : longueur plutôt que classes de caractères, pas d'expiration
forcée, refus des mots de passe courants. La liste ci-dessous est un exemple ; en
production, l'API Pwned Passwords (k-anonymat) la remplacerait.
"""
from __future__ import annotations

import re
import unicodedata

# Mots de passe très utilisés et propres au site, en minuscules
COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "motdepasse",
    "azertyuiop", "qwertyuiop", "azerty123", "qwerty123", "password1",
    "password123", "motdepasse1", "iloveyou", "princess", "admin123",
    "welcome1", "abc12345", "letmein1", "sunshine", "football",
    "hanabi", "hanabi123", "japon123", "boutique", "demo1234",
}

MIN_LENGTH = 10

# bcrypt ignore tout ce qui dépasse 72 octets : deux mots de passe au même début
# ouvriraient le même compte. Limite en octets (« é » en pèse deux). Pré-hacher
# en SHA-256 invaliderait les condensats existants.
MAX_BYTES = 72


def _normalise(raw: str) -> str:
    # NFKC : « ﬁ » et « fi » sont le même secret
    return unicodedata.normalize("NFKC", raw).strip()


def validate_password(raw: str, *, email: str = "", name: str = "") -> str | None:
    """Message d'erreur destiné à l'utilisateur, ou None si le mot de passe convient."""
    pwd = _normalise(raw)

    if len(pwd) < MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {MIN_LENGTH} caractères."
    if len(pwd.encode("utf-8")) > MAX_BYTES:
        return (
            f"Le mot de passe ne peut pas dépasser {MAX_BYTES} caractères. "
            "Les lettres accentuées et les emoji en comptent plusieurs."
        )

    lowered = pwd.lower()

    if lowered in COMMON_PASSWORDS:
        return "Ce mot de passe est trop courant. Choisis-en un moins prévisible."

    if len(set(lowered)) < 5:
        return "Ce mot de passe est trop répétitif. Varie les caractères."
    if re.search(r"(?:0123|1234|2345|3456|4567|5678|6789|abcd|qwer|azer)", lowered):
        return "Évite les suites de touches consécutives."

    local_part = email.split("@")[0].lower() if email else ""
    for personal in (local_part, name.lower()):
        if personal and len(personal) >= 4 and personal in lowered:
            return "Le mot de passe ne doit pas reprendre ton nom ou ton e-mail."

    return None
