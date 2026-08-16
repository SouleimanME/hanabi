"""Jetons a usage unique : confirmation d'adresse, reinitialisation.

TROIS PROPRIETES, ET CHACUNE REPOND A UNE ATTAQUE PRECISE.

  - IMPREVISIBLE. 32 octets tires par `secrets`, soit 256 bits. Un jeton
    devinable, c'est la prise de controle d'un compte sans mot de passe.
  - STOCKE HACHE. La base ne contient que l'empreinte SHA-256 : une copie de la
    base, une sauvegarde qui traine, un journal trop bavard ne donnent aucun
    lien exploitable. Meme raisonnement que pour les mots de passe.
  - A USAGE UNIQUE ET DATE. `utilise_le` ferme la porte des le premier usage,
    et l'expiration borne la fenetre.

POURQUOI PAS UN JETON SIGNE. Un JWT se verifie sans etat, ce qui est seduisant,
mais rien ne l'empeche de resservir tant qu'il n'a pas expire. Un lien de
reinitialisation resterait valable une heure APRES le changement de mot de
passe, y compris dans une boite dont quelqu'un a garde l'acces. L'etat en base
est precisement ce qui permet de le revoquer, et c'est ce qui compte ici.

POURQUOI SHA-256 ET NON BCRYPT, alors que les mots de passe exigent bcrypt. Ce
qui rend un mot de passe attaquable est sa faible entropie et sa reutilisation
d'un site a l'autre ; un condensat lent est la pour rendre chaque essai couteux.
Un jeton de 256 bits n'a ni l'une ni l'autre : il n'existe pas de dictionnaire
de jetons, et l'espace est hors de portee. La lenteur de bcrypt se paierait a
chaque verification sans rien acheter.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import models

log = logging.getLogger("hanabi.jetons")

VERIFICATION = "verification_email"
REINITIALISATION = "reinitialisation"

# Durees de validite. Elles different parce que les deux liens n'ont ni la meme
# urgence ni le meme pouvoir : confirmer une adresse est anodin et peut attendre
# qu'on releve son courrier, reinitialiser un mot de passe donne acces au compte
# et doit se refermer vite.
DUREES = {
    VERIFICATION: timedelta(days=7),
    REINITIALISATION: timedelta(hours=1),
}


def _empreinte(brut: str) -> str:
    return hashlib.sha256(brut.encode()).hexdigest()


def creer(db: Session, user_id: int, usage: str) -> str:
    """Emet un jeton et rend sa forme EN CLAIR, la seule fois ou elle existe.

    L'appelant la place dans le lien du courriel ; la base n'en garde que
    l'empreinte, et personne - pas meme un administrateur - ne peut la retrouver
    ensuite.
    """
    brut = secrets.token_urlsafe(32)

    # Les jetons precedents du meme usage sont revoques. Demander un nouveau
    # lien doit invalider l'ancien : sans cela, un lien intercepte reste
    # utilisable alors que la personne croit l'avoir remplace.
    db.execute(
        update(models.Token)
        .where(
            models.Token.user_id == user_id,
            models.Token.usage == usage,
            models.Token.utilise_le.is_(None),
        )
        .values(utilise_le=models.now_utc())
    )

    db.add(
        models.Token(
            usage=usage,
            user_id=user_id,
            empreinte=_empreinte(brut),
            expire_le=datetime.now(timezone.utc) + DUREES[usage],
        )
    )
    return brut


def consommer(db: Session, brut: str, usage: str) -> models.User | None:
    """Valide le jeton et le brule. Rend le compte, ou `None`.

    Le jeton est marque utilise AVANT que l'appelant n'agisse : si l'action
    echoue ensuite, la transaction entiere est annulee et le jeton redevient
    valable. L'inverse - agir puis marquer - laisserait un jeton reutilisable
    en cas d'echec partiel.
    """
    if not brut:
        return None

    jeton = db.scalar(
        select(models.Token).where(
            models.Token.empreinte == _empreinte(brut),
            models.Token.usage == usage,
        )
    )
    if jeton is None:
        return None
    if jeton.utilise_le is not None:
        log.warning("jeton deja utilise", extra={"usage": usage, "jeton_id": jeton.id})
        return None
    if models.as_utc(jeton.expire_le) < datetime.now(timezone.utc):
        log.info("jeton expire", extra={"usage": usage, "jeton_id": jeton.id})
        return None

    jeton.utilise_le = models.now_utc()
    return db.get(models.User, jeton.user_id)


def purger(db: Session, maintenant: datetime | None = None) -> int:
    """Supprime les jetons expires depuis plus d'une semaine.

    On ne supprime pas des l'expiration : garder un jeton mort quelques jours
    permet de repondre « ce lien a expire » plutot que « lien inconnu », ce qui
    est la difference entre une explication et une enigme.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = maintenant - timedelta(days=7)
    resultat = db.execute(
        models.Token.__table__.delete().where(models.Token.expire_le < limite)
    )
    db.commit()
    return resultat.rowcount or 0
