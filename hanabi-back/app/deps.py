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
    user_id = decode_token(creds.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide ou expire.")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte introuvable.")
    return user


def get_admin_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(creds, db)
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acces reserve aux administrateurs.")
    return user


def is_readonly_admin(user: User) -> bool:
    """Indique si ce compte administrateur est le compte vitrine bride.

    Importe tardivement pour ne pas creer de cycle : `seed` a besoin des
    modeles, qui n'ont pas a connaitre les dependances HTTP.
    """
    from .seed import DEMO_ADMIN_EMAIL

    return bool(
        settings.DEMO_ADMIN_READONLY
        and user.email.strip().lower() == DEMO_ADMIN_EMAIL
    )


def get_admin_writer(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Administrateur autorise a modifier quelque chose.

    Le compte vitrine du back-office a des identifiants publics : quiconque lit
    la fenetre de connexion peut s'y connecter. Lui laisser les droits
    d'ecriture reviendrait a offrir a chaque visiteur la suppression du
    catalogue, la modification des prix et la promotion d'un compte au rang
    d'administrateur.

    Le controle est ici, cote serveur, et non dans l'interface : masquer un
    bouton n'empeche personne d'appeler l'API directement. Le back-office se
    contente de griser ce qui ne servirait a rien, et c'est cette dependance
    qui refuse pour de bon.
    """
    user = get_admin_user(creds, db)
    if is_readonly_admin(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Compte de demonstration : le back-office est consultable, mais pas modifiable.",
        )
    return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if creds is None:
        return None
    user_id = decode_token(creds.credentials)
    return db.get(User, user_id) if user_id else None
