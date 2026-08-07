"""
Politique de mot de passe, appliquee cote serveur.

La jauge de robustesse du navigateur est une aide a la saisie, pas un controle :
un client peut appeler l'API directement et ignorer tout ce que fait la page.
La regle qui compte est donc celle-ci.

Choix suivant les recommandations NIST SP 800-63B, qui vont a l'encontre de
l'habitude des annees 2000 :
  - la longueur primee sur la complexite, car « P@ssw0rd! » satisfait toutes les
    regles de classes de caracteres et figure dans tous les dictionnaires
    d'attaque ;
  - pas d'expiration forcee, qui pousse a des variantes incrementales ;
  - en revanche, refus des mots de passe notoirement compromis.

La liste ci-dessous est volontairement courte et sert d'exemple. En production,
il faut brancher un jeu de donnees de fuites - l'API « Pwned Passwords » de
Have I Been Pwned repond a un prefixe de 5 caracteres du condensat SHA-1, si
bien que le mot de passe complet ne quitte jamais le serveur (k-anonymat).
"""
from __future__ import annotations

import re
import unicodedata

# Mots de passe les plus utilises, et motifs propres a ce site. Normalises en
# minuscules ; la comparaison l'est aussi.
COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "password", "motdepasse",
    "azertyuiop", "qwertyuiop", "azerty123", "qwerty123", "password1",
    "password123", "motdepasse1", "iloveyou", "princess", "admin123",
    "welcome1", "abc12345", "letmein1", "sunshine", "football",
    "hanabi", "hanabi123", "japon123", "boutique", "demo1234",
}

MIN_LENGTH = 10
MAX_LENGTH = 128


def _normalise(raw: str) -> str:
    # NFKC : « ﬁ » et « fi » ne doivent pas compter comme des secrets distincts.
    return unicodedata.normalize("NFKC", raw).strip()


def validate_password(raw: str, *, email: str = "", name: str = "") -> str | None:
    """Renvoie un message d'erreur, ou None si le mot de passe est acceptable.

    Le message est destine a l'utilisateur : il doit dire quoi corriger.
    """
    pwd = _normalise(raw)

    if len(pwd) < MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {MIN_LENGTH} caracteres."
    if len(pwd) > MAX_LENGTH:
        return f"Le mot de passe ne peut pas depasser {MAX_LENGTH} caracteres."

    lowered = pwd.lower()

    if lowered in COMMON_PASSWORDS:
        return "Ce mot de passe est trop courant. Choisis-en un moins previsible."

    # Un seul caractere repete, ou une suite triviale.
    if len(set(lowered)) < 5:
        return "Ce mot de passe est trop repetitif. Varie les caracteres."
    if re.search(r"(?:0123|1234|2345|3456|4567|5678|6789|abcd|qwer|azer)", lowered):
        return "Evite les suites de touches consecutives."

    # Reutiliser son e-mail ou son nom rend le mot de passe devinable par
    # quiconque connait la personne.
    local_part = email.split("@")[0].lower() if email else ""
    for personal in (local_part, name.lower()):
        if personal and len(personal) >= 4 and personal in lowered:
            return "Le mot de passe ne doit pas reprendre ton nom ou ton e-mail."

    return None
