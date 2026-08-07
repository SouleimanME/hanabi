"""Resolution des defis anti-robots pour la suite de tests.

Module separe plutot qu'une fonction dans conftest : les tests peuvent
l'importer directement, sans dependre de l'ordre de chargement des fixtures ni
importer conftest, ce qui est deconseille.
"""
import hashlib

from app import antibot


def solve_antibot(purpose: str) -> dict:
    """Produit un bloc `antibot` valide pour un usage donne.

    Passe par le vrai `issue_challenge`, donc par la vraie signature : les tests
    traversent le code de production et detectent une regression de cablage.
    Le cout reste negligeable car conftest abaisse la difficulte en test.
    """
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
    """Reponse dont on a verifie qu'elle ne satisfait PAS la preuve de travail.

    Prendre une chaine arbitraire ne suffit pas. La difficulte est abaissee a
    quelques bits pendant les tests : une reponse quelconque a environ une
    chance sur seize d'etre valide par accident, ce qui rendait le test du
    refus instable - il echouait quelques fois sur cent, sans rapport avec le
    code teste. On cherche donc explicitement une valeur qui echoue.
    """
    candidat = 0
    while True:
        digest = hashlib.sha256(f"{salt}{candidat}".encode()).digest()
        if antibot._leading_zero_bits(digest) < difficulty:
            return str(candidat)
        candidat += 1
