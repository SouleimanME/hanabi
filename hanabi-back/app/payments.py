"""Autorisation de paiement simulée : aucun prestataire, aucune clé, aucun encaissement.

L'étape reproduit un vrai tunnel pour que les garde-fous autour aient un objet :
- le site ne reçoit qu'un jeton du prestataire, jamais le numéro de carte ;
- l'autorisation peut être refusée (réponse normale) ou rester indécise (délai
  dépassé), le cas qui justifie l'idempotence ;
- la référence d'autorisation est conservée sur la commande.

Des jetons de test déclenchent les échecs à la demande, comme chez les
prestataires réels.
"""
import hashlib
import logging
import secrets
from dataclasses import dataclass

log = logging.getLogger("hanabi.paiement")


class PaiementRefuse(Exception):
    """Refus du prestataire : rien n'a été débité."""

    def __init__(self, motif: str, code: str = "carte_refusee"):
        super().__init__(motif)
        self.motif = motif
        self.code = code


class PaiementIndecis(Exception):
    """Issue inconnue : le débit a peut-être eu lieu. Ne pas rejouer sans clé d'idempotence."""


@dataclass(frozen=True)
class Autorisation:
    reference: str
    montant_cents: int
    reseau: str


# Jetons de test ; tout autre jeton, ou aucun, est accepté
JETON_REFUS = "tok_refus"
JETON_FONDS = "tok_fonds_insuffisants"
JETON_INDECIS = "tok_indecis"


def autoriser(jeton: str | None, montant_cents: int, reference_commande: str) -> Autorisation:
    """Autorise le montant et rend la référence.

    @raises PaiementRefuse: refus, rien n'a été débité
    @raises PaiementIndecis: issue inconnue
    """
    if montant_cents <= 0:
        raise PaiementRefuse("Montant invalide.", code="montant_invalide")

    if jeton == JETON_REFUS:
        raise PaiementRefuse("Carte refusée par la banque émettrice.")
    if jeton == JETON_FONDS:
        raise PaiementRefuse("Provision insuffisante.", code="fonds_insuffisants")
    if jeton == JETON_INDECIS:
        raise PaiementIndecis("Le prestataire n'a pas répondu dans le délai imparti.")

    # Référence déterministe par commande : deux autorisations de la même commande se reconnaissent
    graine = hashlib.sha256(reference_commande.encode()).hexdigest()[:12]
    autorisation = Autorisation(
        reference=f"auth_{graine}",
        montant_cents=montant_cents,
        reseau=_reseau(jeton),
    )
    log.info(
        "paiement autorise",
        extra={
            "reference": autorisation.reference,
            "montant_cents": montant_cents,
            "commande": reference_commande,
        },
    )
    return autorisation


def _reseau(jeton: str | None) -> str:
    """Réseau déduit du jeton, à titre informatif."""
    if not jeton:
        return "simule"
    for nom in ("visa", "mastercard", "amex"):
        if nom in jeton.lower():
            return nom
    return "simule"


def nouvelle_reference_commande() -> str:
    """Numéro de commande tiré par `secrets`, pour qu'il ne se devine pas."""
    return "ATL" + str(secrets.randbelow(900000) + 100000)
