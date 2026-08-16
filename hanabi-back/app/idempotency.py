"""Rejeu sur des requetes qui ne doivent s'executer qu'une fois.

LE CAS REEL. Un acheteur clique deux fois sur « Payer ». Son navigateur rejoue
la requete apres une coupure de reseau. Son telephone reessaie parce que la
reponse a mis trop longtemps a venir. Dans les trois cas, la meme intention
arrive deux fois, et sans garde cela produit deux commandes, deux debits de
stock et deux courriels - alors que la personne n'a rien fait de travers.

LE CONTRAT. Le client tire une cle au hasard AVANT d'envoyer et la repete a
l'identique s'il reessaie, dans l'en-tete `Idempotency-Key`. Le serveur
enregistre la cle avec la reponse produite ; a la deuxieme presentation, il
rejoue cette reponse sans refaire le travail. C'est la convention de Stripe et
de la plupart des API de paiement, reprise telle quelle - un client qui sait
parler a l'une sait parler a celle-ci.

POURQUOI LA CONTRAINTE UNIQUE PLUTOT QU'UN `SELECT` PREALABLE. Entre une lecture
qui ne trouve rien et l'insertion qui suit, une seconde requete peut passer :
c'est exactement ce que fait le double-clic, dont les deux appels partent a
quelques millisecondes d'intervalle. Verifier puis inserer laisse donc passer le
seul cas qu'on cherchait a couvrir. On insere d'emblee, et c'est la base qui
tranche ; le perdant traite la violation d'unicite comme un reessai.

CE QUI RESTE VOLONTAIREMENT HORS DE PORTEE. La cle n'est pas liee au compte :
elle est tiree au hasard sur 128 bits, la deviner n'est pas un chemin d'attaque
credible, et l'y lier empecherait un invite d'en beneficier - or c'est justement
lui qui n'a pas d'historique de commandes pour verifier si son achat est passe.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .config import settings

log = logging.getLogger("hanabi.idempotence")

EN_TETE = "Idempotency-Key"

# Bornes de forme. Une cle sans limite finirait dans un index, et une cle vide
# ferait passer toutes les requetes pour la meme.
LONGUEUR_MIN = 8
LONGUEUR_MAX = 128


class Rejeu(Exception):
    """La requete a deja ete traitee : sa reponse est connue."""

    def __init__(self, code: int, corps: str):
        super().__init__("rejeu")
        self.code = code
        self.corps = corps

    def reponse(self) -> Response:
        return Response(
            content=self.corps,
            status_code=self.code,
            media_type="application/json",
            # En-tete informatif, et utile au diagnostic : il distingue une
            # commande creee d'une commande rejouee, que le corps rend
            # autrement indiscernables.
            headers={"Idempotent-Replay": "true"},
        )


def empreinte(charge: dict) -> str:
    """Empreinte stable du corps de la requete.

    `sort_keys` est indispensable : deux serialisations du meme dictionnaire
    n'ordonnent pas forcement leurs cles, et sans tri un client honnete verrait
    son reessai refuse pour « corps different ».
    """
    return hashlib.sha256(
        json.dumps(charge, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def valider(cle: str | None) -> str | None:
    """Controle la forme de la cle. Son absence est permise."""
    if cle is None:
        return None
    cle = cle.strip()
    if not cle:
        return None
    if not (LONGUEUR_MIN <= len(cle) <= LONGUEUR_MAX):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{EN_TETE} doit compter entre {LONGUEUR_MIN} et {LONGUEUR_MAX} caracteres.",
        )
    if not all(c.isalnum() or c in "-_" for c in cle):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{EN_TETE} n'accepte que des lettres, chiffres, tirets et tirets bas.",
        )
    return cle


def reserver(db: Session, cle: str, point_entree: str, charge: dict) -> models.IdempotencyKey:
    """Prend la cle, ou leve `Rejeu` si elle est deja connue.

    @raises Rejeu: requete deja traitee, sa reponse est rendue telle quelle
    @raises HTTPException: cle reutilisee avec un corps different (422), ou
        requete identique encore en cours (409)
    """
    signature = empreinte(charge)
    trace = models.IdempotencyKey(
        cle=cle, point_entree=point_entree, empreinte=signature, statut="en_cours"
    )
    db.add(trace)
    try:
        # `flush` et non `commit` : la ligne doit exister pour que la contrainte
        # s'applique, mais la transaction reste ouverte pour l'appelant.
        db.flush()
    except IntegrityError:
        db.rollback()
        return _resoudre_conflit(db, cle, point_entree, signature)
    return trace


def _resoudre_conflit(db: Session, cle: str, point_entree: str, signature: str) -> models.IdempotencyKey:
    """Statue sur une cle deja prise."""
    existante = db.scalar(
        select(models.IdempotencyKey).where(
            models.IdempotencyKey.cle == cle,
            models.IdempotencyKey.point_entree == point_entree,
        )
    )
    if existante is None:
        # La ligne concurrente a ete annulee entre la violation et cette
        # lecture. Rare, mais possible : on laisse l'appelant retenter.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Requete concurrente en cours, reessaie dans un instant."
        )

    if existante.empreinte != signature:
        # Ce n'est pas un reessai mais une cle reutilisee par megarde. Renvoyer
        # la reponse de l'autre achat serait le pire des comportements : le
        # client croirait sa commande passee.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Cette {EN_TETE} a deja servi pour une requete differente.",
        )

    if existante.statut == "en_cours":
        # Le premier appel n'a pas fini. Le client doit attendre, pas relancer :
        # c'est ce que dit un 409, la ou un 500 l'inviterait a reessayer tout de
        # suite et a empiler les tentatives.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Une requete identique est en cours de traitement.",
        )

    log.info("rejeu servi", extra={"cle": cle, "point_entree": point_entree})
    raise Rejeu(existante.code_reponse or 200, existante.corps_reponse or "{}")


def conclure(db: Session, trace: models.IdempotencyKey, code: int, corps: str) -> None:
    """Enregistre la reponse produite, pour la rejouer si besoin."""
    trace.statut = "termine"
    trace.code_reponse = code
    trace.corps_reponse = corps


def purger(db: Session, maintenant: datetime | None = None) -> int:
    """Oublie les cles expirees. Rend le nombre de lignes supprimees.

    Sans purge, la table croit indefiniment : elle n'est qu'un journal de
    requetes, et sa seule raison d'exister est la fenetre pendant laquelle un
    client peut encore reessayer.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = maintenant - timedelta(hours=settings.IDEMPOTENCE_RETENTION_HEURES)
    resultat = db.execute(
        delete(models.IdempotencyKey).where(models.IdempotencyKey.created_at < limite)
    )
    db.commit()
    return resultat.rowcount or 0
