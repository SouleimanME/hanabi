"""Jetons à usage unique : confirmation d'adresse, réinitialisation.

- 32 octets tirés par `secrets` ;
- stockés hachés (SHA-256) : une copie de la base ne donne aucun lien valable.
  bcrypt n'apporterait rien sur 256 bits aléatoires ;
- à usage unique et datés. En base plutôt que signés, pour qu'un lien de
  réinitialisation meure dès qu'il a servi.
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

# Confirmer une adresse peut attendre ; réinitialiser un mot de passe se referme vite
DUREES = {
    VERIFICATION: timedelta(days=7),
    REINITIALISATION: timedelta(hours=1),
}


def _empreinte(brut: str) -> str:
    return hashlib.sha256(brut.encode()).hexdigest()


def creer(db: Session, user_id: int, usage: str) -> str:
    """Émet un jeton et rend sa forme en clair, qui n'est conservée nulle part."""
    brut = secrets.token_urlsafe(32)

    # Un nouveau lien invalide les précédents du même usage
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
    """Valide et brûle le jeton ; rend le compte ou `None`.

    Marqué utilisé avant l'action : si elle échoue, la transaction annulée le
    rend de nouveau valable.
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
    """Supprime les jetons expirés depuis plus d'une semaine.

    Le délai permet de répondre « lien expiré » plutôt que « lien inconnu ».
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = maintenant - timedelta(days=7)
    resultat = db.execute(
        models.Token.__table__.delete().where(models.Token.expire_le < limite)
    )
    db.commit()
    return resultat.rowcount or 0
