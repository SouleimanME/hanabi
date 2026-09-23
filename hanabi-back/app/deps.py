from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")
    lu = decode_token(creds.credentials)
    if lu is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide ou expiré.")
    user_id, generation = lu
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte introuvable.")
    # Jeton émis avant une révocation : même message qu'un jeton expiré
    if int(user.token_version or 0) != generation:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide ou expiré.")
    return user


def get_admin_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(creds, db)
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès réservé aux administrateurs.")
    return user


def is_readonly_admin(user: User) -> bool:
    """Vrai pour le compte back-office de démonstration bridé (import tardif : évite un cycle)."""
    from .seed import DEMO_ADMIN_EMAIL

    return bool(
        settings.DEMO_ADMIN_READONLY
        and user.email.strip().lower() == DEMO_ADMIN_EMAIL
    )


def get_admin_writer(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Administrateur autorisé à écrire. Refuse le compte de démonstration, côté serveur."""
    user = get_admin_user(creds, db)
    if is_readonly_admin(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Compte de démonstration : le back-office est consultable, mais pas modifiable.",
        )
    return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if creds is None:
        return None
    lu = decode_token(creds.credentials)
    if lu is None:
        return None
    user_id, generation = lu
    user = db.get(User, user_id)
    # Même contrôle de génération que sur la voie obligatoire
    if user is None or int(user.token_version or 0) != generation:
        return None
    return user
