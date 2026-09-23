"""Gestion de son propre compte : profil, identifiants, moyens de paiement, RGPD.

Aucune route ne prend d'identifiant de compte : elles agissent sur le porteur du
jeton. Modifier le contenu du compte demande d'être connecté ; modifier ce qui en
donne l'accès (mot de passe, e-mail) exige en plus le mot de passe courant.
"""
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import emails, models, outbox, rgpd, schemas, tokens
from ..database import get_db
from ..deps import get_current_user
from ..passwords import validate_password
from ..ratelimit import limiter
from ..security import hash_password, verify_password
from .auth import compte_par_email

# Écritures plafonnées selon leur coût ; la lecture relève de la limite globale.

log = logging.getLogger("hanabi.compte")

router = APIRouter(prefix="/compte", tags=["compte"])

MAX_MOYENS_PAIEMENT = 8


# --- Profil ---

# Champs facultatifs qu'une chaîne vide efface ; `name` reste obligatoire
EFFACABLES = {"civility", "birthdate", "phone", "addr", "addr_extra", "cp", "city"}


@router.patch("/profil", response_model=schemas.UserOut)
@limiter.limit("20/minute")
def modifier_profil(
    request: Request,
    data: schemas.ProfilPatch,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Modifie les seuls champs fournis (`exclude_unset` : absent n'est pas vide)."""
    changements = data.model_dump(exclude_unset=True)
    if not changements:
        return user

    for champ, valeur in changements.items():
        if isinstance(valeur, str):
            valeur = valeur.strip()
        if valeur == "" and champ in EFFACABLES:
            valeur = None
        elif valeur == "":
            # Champ obligatoire laissé vide : ignoré
            continue
        setattr(user, champ, valeur)

    db.commit()
    db.refresh(user)
    log.info("profil modifie", extra={"compte": user.id, "champs": sorted(changements)})
    return user


@router.post("/mot-de-passe", status_code=204)
@limiter.limit("5/minute")
def changer_mot_de_passe(
    request: Request,
    data: schemas.ChangePasswordIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Change le mot de passe, l'ancien à l'appui."""
    if not verify_password(data.ancien, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe actuel incorrect.")

    if data.nouveau == data.ancien:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Le nouveau mot de passe doit différer de l'ancien.",
        )

    probleme = validate_password(data.nouveau, email=user.email, name=user.name)
    if probleme:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, probleme)

    user.password_hash = hash_password(data.nouveau)

    # Révoque toutes les sessions, y compris la courante : un jeton déjà émis
    # resterait sinon valable douze heures.
    user.token_version = int(user.token_version or 0) + 1

    # Et les liens de réinitialisation encore valides
    db.execute(
        update(models.Token)
        .where(
            models.Token.user_id == user.id,
            models.Token.usage == tokens.REINITIALISATION,
            models.Token.utilise_le.is_(None),
        )
        .values(utilise_le=models.now_utc())
    )
    db.commit()
    log.warning("mot de passe change", extra={"compte": user.id})


@router.post("/email", response_model=schemas.UserOut)
@limiter.limit("5/minute")
def changer_email(
    request: Request,
    data: schemas.ChangeEmailIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Change l'adresse de connexion, mot de passe à l'appui.

    La nouvelle adresse repart non confirmée, avec un lien envoyé dessus.
    """
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe incorrect.")

    nouvelle = data.email
    if nouvelle == user.email.lower():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "C'est déjà ton adresse.")

    if compte_par_email(db, nouvelle) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cet e-mail.")

    user.email = nouvelle
    user.email_verified = False

    jeton = tokens.creer(db, user.id, tokens.VERIFICATION)
    sujet, texte, html = emails.confirmation_adresse(user, jeton)
    outbox.deposer(db, nouvelle, sujet, texte, html)

    db.commit()
    db.refresh(user)
    # L'ancienne adresse n'est pas journalisée
    log.warning("adresse changee", extra={"compte": user.id, "confirmee": False})
    return user


# --- Moyens de paiement ---


@router.get("/paiements", response_model=list[schemas.MoyenPaiementOut])
def lister_paiements(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return db.scalars(
        select(models.PaymentMethod)
        .where(models.PaymentMethod.user_id == user.id)
        .order_by(models.PaymentMethod.defaut.desc(), models.PaymentMethod.id.desc())
    ).all()


@router.post("/paiements", response_model=schemas.MoyenPaiementOut, status_code=201)
@limiter.limit("10/minute")
def ajouter_paiement(
    request: Request,
    data: schemas.MoyenPaiementIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Enregistre une carte sans jamais recevoir son numéro.

    Le jeton est émis ici faute de prestataire réel ; il viendrait sinon du
    composant du prestataire dans le navigateur.
    """
    total = db.scalar(
        select(func.count()).select_from(models.PaymentMethod).where(
            models.PaymentMethod.user_id == user.id
        )
    )
    if total >= MAX_MOYENS_PAIEMENT:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Maximum {MAX_MOYENS_PAIEMENT} moyens de paiement enregistrés.",
        )

    moyen = models.PaymentMethod(
        user_id=user.id,
        reseau=data.reseau,
        quatre_derniers=data.quatre_derniers,
        exp_mois=data.exp_mois,
        exp_annee=data.exp_annee,
        libelle=(data.libelle or "").strip() or None,
        jeton=f"pm_{secrets.token_urlsafe(24)}",
        # La première carte devient la carte par défaut
        defaut=data.defaut or total == 0,
    )
    db.add(moyen)
    db.flush()

    if moyen.defaut:
        _demarquer_les_autres(db, user.id, moyen.id)

    db.commit()
    db.refresh(moyen)
    log.info(
        "moyen de paiement ajoute",
        extra={"compte": user.id, "reseau": moyen.reseau, "defaut": moyen.defaut},
    )
    return moyen


@router.post("/paiements/{moyen_id}/defaut", response_model=schemas.MoyenPaiementOut)
@limiter.limit("20/minute")
def definir_defaut(
    request: Request,
    moyen_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    moyen = _sien(db, user, moyen_id)
    moyen.defaut = True
    _demarquer_les_autres(db, user.id, moyen.id)
    db.commit()
    db.refresh(moyen)
    return moyen


@router.delete("/paiements/{moyen_id}", status_code=204)
@limiter.limit("20/minute")
def supprimer_paiement(
    request: Request,
    moyen_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    moyen = _sien(db, user, moyen_id)
    etait_defaut = moyen.defaut
    db.delete(moyen)
    db.flush()

    # La carte la plus récente reprend le rôle de carte par défaut
    if etait_defaut:
        suivante = db.scalar(
            select(models.PaymentMethod)
            .where(models.PaymentMethod.user_id == user.id)
            .order_by(models.PaymentMethod.id.desc())
        )
        if suivante is not None:
            suivante.defaut = True

    db.commit()
    log.info("moyen de paiement supprime", extra={"compte": user.id})


def _sien(db: Session, user: models.User, moyen_id: int) -> models.PaymentMethod:
    """Moyen de paiement du demandeur, filtré dans la requête. 404 sinon, jamais 403."""
    moyen = db.scalar(
        select(models.PaymentMethod).where(
            models.PaymentMethod.id == moyen_id,
            models.PaymentMethod.user_id == user.id,
        )
    )
    if moyen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Moyen de paiement introuvable.")
    return moyen


def _demarquer_les_autres(db: Session, user_id: int, garde_id: int) -> None:
    """Une seule carte par défaut par compte (SQLite n'a pas d'index unique partiel)."""
    db.execute(
        update(models.PaymentMethod)
        .where(
            models.PaymentMethod.user_id == user_id,
            models.PaymentMethod.id != garde_id,
        )
        .values(defaut=False)
    )


# --- Droits RGPD : portabilité (art. 20) et effacement (art. 17) ---


@router.post("/export")
@limiter.limit("3/hour")
def exporter_mes_donnees(
    request: Request,
    data: schemas.MotDePasseIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Toutes les données du compte, mot de passe à l'appui (l'export rassemble tout)."""
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe incorrect.")

    log.info("export de donnees", extra={"compte": user.id})
    return rgpd.exporter(db, user)


@router.post("/suppression", status_code=200)
@limiter.limit("3/hour")
def supprimer_mon_compte(
    request: Request,
    data: schemas.SuppressionIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Droit à l'effacement, irréversible.

    Mot de passe et formule recopiée. Le compte est anonymisé, pas supprimé : les
    commandes restent pour l'obligation comptable (Code de commerce L123-22,
    RGPD art. 17-3-b). Détail dans `app/rgpd.py`.
    """
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe incorrect.")

    if data.confirmation.strip().upper() != rgpd.FORMULE_CONFIRMATION:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Recopie exactement « {rgpd.FORMULE_CONFIRMATION} » pour confirmer.",
        )

    # Un administrateur pourrait fermer le back-office derrière lui
    if user.is_admin:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Un compte administrateur ne peut pas s'effacer lui-même. "
            "Retire d'abord les droits d'administration.",
        )

    bilan = rgpd.anonymiser(db, user)
    db.commit()

    return {
        "ok": True,
        "message": (
            "Ton compte a été effacé. Tes commandes sont conservées sans aucune "
            "donnée personnelle : la loi impose de garder dix ans les pièces "
            "comptables, et le RGPD le prévoit."
        ),
        "efface": bilan,
        "note_avis": (
            "Le texte de tes avis reste en ligne sous un auteur anonyme. Si l'un "
            "d'eux contient une information personnelle, écris-nous pour le faire "
            "retirer."
        ),
    }
