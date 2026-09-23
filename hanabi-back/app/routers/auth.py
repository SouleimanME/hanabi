import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import emails, models, outbox, schemas, tokens
from ..antibot import check_throttle, clear_failures, record_failure, verify as verify_antibot
from ..database import get_db
from ..deps import get_current_user
from ..passwords import validate_password
from ..ratelimit import limiter
from ..security import hash_password, verify_password, create_access_token

log = logging.getLogger("hanabi.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

# Condensat d'un mot de passe de personne : égalise le temps de réponse de /login
_DUMMY_HASH = hash_password("hanabi-timing-equalizer")


def compte_par_email(db: Session, email: str) -> models.User | None:
    """Compte d'une adresse déjà en minuscules.

    Égalité exacte d'abord (index). Repli insensible à la casse pour les rares
    comptes que la migration n'a pas pu ramener en minuscules.
    """
    compte = db.query(models.User).filter(models.User.email == email).first()
    if compte is None:
        compte = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    return compte


def _ou_rien(valeur: str | None) -> str | None:
    """Champ facultatif : une chaîne vide n'est pas une valeur."""
    valeur = (valeur or "").strip()
    return valeur or None


@router.post("/register", response_model=schemas.TokenOut, status_code=201)
@limiter.limit("5/minute")
def register(request: Request, data: schemas.RegisterIn, db: Session = Depends(get_db)):
    verify_antibot(data.antibot, "register")

    problem = validate_password(data.password, email=data.email, name=data.name)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    if compte_par_email(db, data.email) is not None:
        # Révèle l'existence du compte ; compromis accepté, freiné par la preuve
        # de travail et la limite de débit.
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cet e-mail.")

    user = models.User(
        name=data.name.strip(), email=data.email, password_hash=hash_password(data.password),
        civility=data.civility, birthdate=_ou_rien(data.birthdate),
        phone=_ou_rien(data.phone), addr=_ou_rien(data.addr),
        addr_extra=_ou_rien(data.addr_extra),
        cp=_ou_rien(data.cp), city=_ou_rien(data.city),
    )
    db.add(user)
    # Compte, jeton et courriel dans la même transaction
    db.flush()

    jeton = tokens.creer(db, user.id, tokens.VERIFICATION)
    sujet, texte, html = emails.confirmation_adresse(user, jeton)
    outbox.deposer(db, user.email, sujet, texte, html)

    db.commit()
    db.refresh(user)
    return schemas.TokenOut(access_token=create_access_token(user), user=user)


@router.post("/verify-email", response_model=schemas.UserOut)
@limiter.limit("10/minute")
def verify_email(request: Request, data: schemas.VerifyEmailIn, db: Session = Depends(get_db)):
    """Confirme une adresse depuis le lien reçu ; le jeton suffit comme preuve."""
    user = tokens.consommer(db, data.jeton, tokens.VERIFICATION)
    if user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ce lien de confirmation est invalide ou a expiré. Demande-en un nouveau.",
        )

    user.email_verified = True
    db.commit()
    db.refresh(user)
    log.info("adresse confirmee", extra={"compte": user.id})
    return user


@router.post("/resend-verification", status_code=202)
@limiter.limit("3/minute")
def resend_verification(
    request: Request, db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Renvoie un lien de confirmation, au seul compte connecté."""
    if user.email_verified:
        return {"ok": True, "deja_confirmee": True}

    jeton = tokens.creer(db, user.id, tokens.VERIFICATION)
    sujet, texte, html = emails.confirmation_adresse(user, jeton)
    outbox.deposer(db, user.email, sujet, texte, html)
    db.commit()
    return {"ok": True, "deja_confirmee": False}


@router.post("/forgot-password", status_code=202)
@limiter.limit("3/minute")
def forgot_password(
    request: Request, data: schemas.ForgotPasswordIn, db: Session = Depends(get_db)
):
    """Envoie un lien de réinitialisation si le compte existe.

    Répond toujours 202 avec le même message, pour ne pas révéler quelles
    adresses ont un compte.
    """
    user = compte_par_email(db, data.email)

    if user is not None:
        jeton = tokens.creer(db, user.id, tokens.REINITIALISATION)
        sujet, texte, html = emails.reinitialisation_mot_de_passe(user, jeton)
        outbox.deposer(db, user.email, sujet, texte, html)
        db.commit()
        log.info("reinitialisation demandee", extra={"compte": user.id})
    else:
        log.info("reinitialisation demandee pour une adresse inconnue")

    return {
        "ok": True,
        "message": "Si un compte existe pour cette adresse, un lien vient d'y être envoyé.",
    }


@router.post("/reset-password", response_model=schemas.TokenOut)
@limiter.limit("5/minute")
def reset_password(
    request: Request, data: schemas.ResetPasswordIn, db: Session = Depends(get_db)
):
    """Fixe un nouveau mot de passe depuis le lien reçu, puis connecte."""
    user = tokens.consommer(db, data.jeton, tokens.REINITIALISATION)
    if user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ce lien est invalide, a expiré ou a déjà servi. Demande-en un nouveau.",
        )

    problem = validate_password(data.password, email=user.email, name=user.name)
    if problem:
        # Rollback : le jeton reste valable pour un nouvel essai
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    user.password_hash = hash_password(data.password)
    # L'accès à la boîte est prouvé
    user.email_verified = True
    # Toutes les autres sessions tombent ; le jeton rendu porte la nouvelle génération
    user.token_version = int(user.token_version or 0) + 1

    clear_failures(f"email:{user.email.lower()}")
    clear_failures(f"ip:{get_remote_address(request)}")

    db.commit()
    db.refresh(user)
    log.warning("mot de passe reinitialise", extra={"compte": user.id})

    return schemas.TokenOut(access_token=create_access_token(user), user=user)


@router.post("/login", response_model=schemas.TokenOut)
@limiter.limit("10/minute")
def login(request: Request, data: schemas.LoginIn, db: Session = Depends(get_db)):
    verify_antibot(data.antibot, "login")

    # Compteur par e-mail en plus de l'IP : un bourrage d'identifiants réparti sur
    # de nombreuses adresses vise quand même le même compte.
    email_key = f"email:{data.email}"
    ip_key = f"ip:{get_remote_address(request)}"
    check_throttle(email_key)
    check_throttle(ip_key)

    user = compte_par_email(db, data.email)

    # bcrypt sur un condensat factice : un e-mail inconnu ne répond pas plus vite
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
    token = create_access_token(user)
    return schemas.TokenOut(access_token=token, user=user)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user
