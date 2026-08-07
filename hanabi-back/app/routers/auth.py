from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from .. import models, schemas
from ..antibot import check_throttle, clear_failures, record_failure, verify as verify_antibot
from ..database import get_db
from ..deps import get_current_user
from ..passwords import validate_password
from ..ratelimit import limiter
from ..security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Condensat bcrypt d'un mot de passe qui n'est celui de personne. Sert a
# consommer le meme temps de calcul lorsque l'e-mail est inconnu (voir login).
_DUMMY_HASH = hash_password("hanabi-timing-equalizer")


@router.post("/register", response_model=schemas.TokenOut, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, data: schemas.RegisterIn, db: Session = Depends(get_db)):
    verify_antibot(data.antibot, "register")

    problem = validate_password(data.password, email=str(data.email), name=data.name)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    exists = db.query(models.User).filter(models.User.email == data.email).first()
    if exists:
        # Compromis assume : ce message revele qu'un compte existe pour cet
        # e-mail. C'est une fuite d'information (enumeration de comptes), mais
        # la taire obligerait a un parcours par courriel que ce projet n'a pas,
        # et laisserait l'utilisateur sans explication. Le cout est limite par
        # la preuve de travail et la limite de 5 essais par minute.
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe deja avec cet e-mail.")

    user = models.User(
        name=data.name, email=str(data.email), password_hash=hash_password(data.password),
        civility=data.civility, birthdate=data.birthdate,
        phone=data.phone, addr=data.addr, addr_extra=data.addr_extra,
        cp=data.cp, city=data.city,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return schemas.TokenOut(access_token=token, user=user)


@router.post("/login", response_model=schemas.TokenOut)
@limiter.limit("10/minute")
def login(request: Request, data: schemas.LoginIn, db: Session = Depends(get_db)):
    verify_antibot(data.antibot, "login")

    # Deux compteurs distincts. La limite de slowapi est indexee sur l'IP et ne
    # freine pas un bourrage d'identifiants reparti sur des milliers d'adresses,
    # qui ne tente que quelques mots de passe par IP mais des milliers sur un
    # meme compte. La cle par e-mail couvre ce cas.
    email_key = f"email:{str(data.email).lower()}"
    ip_key = f"ip:{get_remote_address(request)}"
    check_throttle(email_key)
    check_throttle(ip_key)

    user = db.query(models.User).filter(models.User.email == data.email).first()

    # Verifier un condensat factice quand l'e-mail est inconnu egalise le temps
    # de reponse. Sans cela, une reponse instantanee signifie « cet e-mail n'a
    # pas de compte » et le message generique ne protege plus de rien : bcrypt
    # est lent par construction, l'ecart est mesurable a distance.
    if user is None:
        verify_password(data.password, _DUMMY_HASH)
        ok = False
    else:
        ok = verify_password(data.password, user.password_hash)

    if not ok:
        record_failure(email_key)
        record_failure(ip_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou mot de passe incorrect.")

    clear_failures(email_key)
    clear_failures(ip_key)
    token = create_access_token(user.id)
    return schemas.TokenOut(access_token=token, user=user)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user
