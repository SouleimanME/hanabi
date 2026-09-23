"""Resolution des defis anti-robots pour la suite de tests."""
import hashlib

from app import antibot


def solve_antibot(purpose: str) -> dict:
    """Produit un bloc `antibot` valide pour un usage donne."""
    challenge = antibot.issue_challenge(purpose)
    nonce = 0
    while True:
        digest = hashlib.sha256(f"{challenge.salt}{nonce}".encode()).digest()
        if antibot._leading_zero_bits(digest) >= challenge.difficulty:
            break
        nonce += 1
    return {
        "salt": challenge.salt,
        "issued_at": challenge.issued_at,
        "signature": challenge.signature,
        "nonce": str(nonce),
        "honeypot": "",
    }


def wrong_nonce(salt: str, difficulty: int) -> str:
    """Reponse dont on a verifie qu'elle ne satisfait pas la preuve de travail."""
    candidat = 0
    while True:
        digest = hashlib.sha256(f"{salt}{candidat}".encode()).digest()
        if antibot._leading_zero_bits(digest) < difficulty:
            return str(candidat)
        candidat += 1
