"""Autorisation de paiement simulee.

AUCUN ARGENT NE CIRCULE. Cette boutique est fictive, et le rester est une
decision, pas une limite technique. Ce module ne parle a aucun prestataire, ne
detient aucune cle, et ne saurait pas encaisser un centime.

Alors pourquoi l'ecrire. Parce que sans etape de paiement, l'idempotence n'a
rien a proteger : rejouer une requete qui ne fait qu'inserer une ligne est
ennuyeux, rejouer une requete qui debite une carte ne l'est pas. Le decoupage
qui suit est celui d'un vrai tunnel d'achat, et c'est lui qui donne leur sens
aux garde-fous places autour.

Ce qui est reproduit fidelement :

  - Le site ne voit JAMAIS le numero de carte. Il recoit un jeton emis par le
    formulaire du prestataire (`payment_token`), ce qui maintient l'application
    hors du perimetre PCI-DSS. Le schema `CheckoutIn` le prevoit deja.
  - L'autorisation precede la confirmation, et peut echouer. Un refus n'est pas
    une panne : c'est une reponse normale, a traduire en message clair.
  - Certains echecs sont AMBIGUS. Un delai d'attente depasse ne dit pas si le
    debit a eu lieu. C'est le cas qui justifie a lui seul l'idempotence : le
    client reessaie, et le serveur doit reconnaitre la seconde tentative comme
    la meme intention.
  - La reference d'autorisation est conservee sur la commande, seul moyen de
    rapprocher plus tard une commande d'un mouvement bancaire.

Les jetons de test suivent la convention des prestataires reels - Stripe
distribue de la meme facon des numeros qui echouent a la demande - pour que les
chemins d'echec soient jouables sans attendre qu'ils surviennent.
"""
import hashlib
import logging
import secrets
from dataclasses import dataclass

log = logging.getLogger("hanabi.paiement")


class PaiementRefuse(Exception):
    """Le prestataire a refuse. L'issue est connue : rien n'a ete debite."""

    def __init__(self, motif: str, code: str = "carte_refusee"):
        super().__init__(motif)
        self.motif = motif
        self.code = code


class PaiementIndecis(Exception):
    """L'issue est INCONNUE : le debit a peut-etre eu lieu.

    Distincte de `PaiementRefuse` a dessein. Un refus permet de rendre le stock
    et d'inviter a recommencer ; une issue indecise l'interdit, puisque
    recommencer pourrait debiter une seconde fois. C'est precisement la que la
    cle d'idempotence gagne sa place.
    """


@dataclass(frozen=True)
class Autorisation:
    reference: str
    montant_cents: int
    reseau: str


# Jetons de test. Tout autre jeton - et l'absence de jeton - est accepte.
JETON_REFUS = "tok_refus"
JETON_FONDS = "tok_fonds_insuffisants"
JETON_INDECIS = "tok_indecis"


def autoriser(jeton: str | None, montant_cents: int, reference_commande: str) -> Autorisation:
    """Demande l'autorisation du montant, et rend sa reference.

    @raises PaiementRefuse: refus franc, rien n'a ete debite
    @raises PaiementIndecis: issue inconnue, ne pas rejouer sans cle d'idempotence
    """
    if montant_cents <= 0:
        raise PaiementRefuse("Montant invalide.", code="montant_invalide")

    if jeton == JETON_REFUS:
        raise PaiementRefuse("Carte refusee par la banque emettrice.")
    if jeton == JETON_FONDS:
        raise PaiementRefuse("Provision insuffisante.", code="fonds_insuffisants")
    if jeton == JETON_INDECIS:
        raise PaiementIndecis("Le prestataire n'a pas repondu dans le delai imparti.")

    # Reference deterministe pour une meme commande, comme le ferait un
    # prestataire a qui l'on transmet sa propre reference : deux autorisations
    # de la meme commande se reconnaissent au lieu de produire deux mouvements
    # indiscernables.
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
    """Reseau declare par le jeton, sans valeur autre qu'informative."""
    if not jeton:
        return "simule"
    for nom in ("visa", "mastercard", "amex"):
        if nom in jeton.lower():
            return nom
    return "simule"


def nouvelle_reference_commande() -> str:
    """Numero de commande. `secrets` plutot que `random` : il ne se devine pas."""
    return "ATL" + str(secrets.randbelow(900000) + 100000)
