import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi.util import get_remote_address
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
    # `flush` et non `commit` : il faut l'identifiant du compte pour emettre le
    # jeton, mais le compte, le jeton et le courriel doivent etre valides
    # ensemble. Un compte cree sans son courriel de confirmation laisserait
    # quelqu'un attendre un message qui ne viendra jamais.
    db.flush()

    jeton = tokens.creer(db, user.id, tokens.VERIFICATION)
    sujet, texte, html = emails.confirmation_adresse(user, jeton)
    outbox.deposer(db, user.email, sujet, texte, html)

    db.commit()
    db.refresh(user)
    return schemas.TokenOut(access_token=create_access_token(user.id), user=user)


@router.post("/verify-email", response_model=schemas.UserOut)
@limiter.limit("10/minute")
def verify_email(request: Request, data: schemas.VerifyEmailIn, db: Session = Depends(get_db)):
    """Confirme une adresse a partir du lien recu.

    Aucune authentification requise : la personne clique depuis sa boite, pas
    depuis le site, et exiger une session la renverrait vers un formulaire de
    connexion au milieu du parcours. Le jeton EST la preuve - il n'a ete envoye
    qu'a cette adresse.
    """
    user = tokens.consommer(db, data.jeton, tokens.VERIFICATION)
    if user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ce lien de confirmation est invalide ou a expire. Demande-en un nouveau.",
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
    """Renvoie un lien de confirmation au compte connecte.

    Reserve au compte connecte, contrairement aux autres routes de ce fichier :
    ouverte, elle permettrait d'inonder la boite de n'importe quel inscrit en
    repostant son adresse.
    """
    if user.email_verified:
        # Pas une erreur : l'adresse est confirmee, l'intention est satisfaite.
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
    """Envoie un lien de reinitialisation, si le compte existe.

    REPOND TOUJOURS 202, compte connu ou non. C'est la seule facon de ne pas
    transformer ce formulaire en detecteur d'adresses : repondre 404 sur une
    adresse inconnue permettrait de tester une liste entiere et d'en extraire
    les clients de la boutique. Le contraste avec `/register` est assume - la,
    taire l'existence du compte laisserait l'utilisateur sans explication devant
    un formulaire qui refuse ; ici, le message est le meme dans les deux cas et
    n'empeche personne d'avancer.

    L'inscription reste donc enumerable, et c'est la limite acceptee. Ce qui ne
    se justifierait pas serait d'ouvrir une SECONDE porte, sans contrepartie.
    """
    email = str(data.email).lower()
    user = db.query(models.User).filter(models.User.email == email).first()

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
        "message": "Si un compte existe pour cette adresse, un lien vient d'y etre envoye.",
    }


@router.post("/reset-password", response_model=schemas.TokenOut)
@limiter.limit("5/minute")
def reset_password(
    request: Request, data: schemas.ResetPasswordIn, db: Session = Depends(get_db)
):
    """Fixe un nouveau mot de passe a partir du lien recu."""
    user = tokens.consommer(db, data.jeton, tokens.REINITIALISATION)
    if user is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ce lien est invalide, a expire ou a deja servi. Demande-en un nouveau.",
        )

    # Meme politique qu'a l'inscription : un parcours de recuperation n'est pas
    # une occasion d'accepter un mot de passe plus faible.
    problem = validate_password(data.password, email=user.email, name=user.name)
    if problem:
        # La transaction est annulee, donc le jeton n'est PAS consomme : sinon
        # un premier essai refuse pour cause de mot de passe trop court brulerait
        # le lien, et il faudrait tout recommencer depuis la boite mail.
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    user.password_hash = hash_password(data.password)
    # Reprendre la main sur son mot de passe prouve l'acces a la boite : si
    # l'adresse n'etait pas encore confirmee, elle l'est de fait.
    user.email_verified = True

    # Les compteurs d'echec sont remis a zero : quelqu'un qui vient de prouver
    # son acces ne doit pas rester bloque par les tentatives ratees qui l'ont
    # conduit ici.
    clear_failures(f"email:{user.email.lower()}")
    clear_failures(f"ip:{get_remote_address(request)}")

    db.commit()
    db.refresh(user)
    log.warning("mot de passe reinitialise", extra={"compte": user.id})

    # Connecte dans la foulee : renvoyer vers l'ecran de connexion apres avoir
    # prouve son identite et choisi un mot de passe est une etape de trop.
    return schemas.TokenOut(access_token=create_access_token(user.id), user=user)


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
