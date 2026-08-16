"""Gestion de son propre compte : profil, identifiants, moyens de paiement.

TOUT EST PORTE PAR LA SESSION. Aucune de ces routes ne prend d'identifiant de
compte : elles agissent sur le porteur du jeton, et sur lui seul. C'est ce qui
rend impossible la classe de faille la plus banale de ces ecrans - passer
`?user_id=2` et modifier le compte du voisin. Il n'y a pas de parametre a
falsifier parce qu'il n'y a pas de parametre.

DEUX NIVEAUX D'EXIGENCE, et la frontiere n'est pas arbitraire :

  - modifier le CONTENU du compte (nom, adresse, telephone) demande d'etre
    connecte ;
  - modifier ce qui donne l'ACCES au compte (mot de passe, adresse e-mail)
    demande en plus le mot de passe courant.

La raison est concrete : un poste laisse ouvert quelques minutes suffirait
autrement a verrouiller definitivement le proprietaire hors de chez lui. Une
session prouve qu'on etait la il y a douze heures, pas qu'on est la maintenant.
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

# TOUTES LES ROUTES D'ECRITURE SONT PLAFONNEES.
#
# Etre authentifie n'est pas une autorisation d'ecrire sans fin : un jeton vole,
# ou simplement un script maladroit, peut marteler ces routes autant que
# n'importe qui. Les plafonds different selon ce que l'abus coute - changer un
# mot de passe est une operation lente (bcrypt) et sensible, modifier son
# telephone ne l'est pas.
#
# La lecture n'est pas plafonnee : elle ne cree rien et le cout d'un abus se
# limite a la charge, que la limite globale de slowapi couvre deja.

log = logging.getLogger("hanabi.compte")

router = APIRouter(prefix="/compte", tags=["compte"])

# Une carte de plus ne coute rien, mais une liste sans fin transforme le choix du
# paiement en corvee et ouvre une ecriture illimitee sur un compte.
MAX_MOYENS_PAIEMENT = 8


# --------------------------------------------------------------------------
# Profil
# --------------------------------------------------------------------------

# Champs facultatifs : une chaine vide les efface. `name` n'en fait pas partie,
# un compte sans nom n'a pas de sens.
EFFACABLES = {"civility", "birthdate", "phone", "addr", "addr_extra", "cp", "city"}


@router.patch("/profil", response_model=schemas.UserOut)
@limiter.limit("20/minute")
def modifier_profil(
    request: Request,
    data: schemas.ProfilPatch,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Modifie les champs fournis, et EUX SEULS.

    `exclude_unset` distingue « champ absent » de « champ a vide ». Sans lui, un
    formulaire qui n'envoie que le telephone effacerait l'adresse, la ville et le
    code postal - tous absents du corps, donc tous vus comme `None`.
    """
    changements = data.model_dump(exclude_unset=True)
    if not changements:
        return user

    for champ, valeur in changements.items():
        if isinstance(valeur, str):
            valeur = valeur.strip()
        # Chaine vide sur un champ effacable : c'est une suppression voulue.
        if valeur == "" and champ in EFFACABLES:
            valeur = None
        elif valeur == "":
            # Sur un champ obligatoire, une chaine vide est une erreur de saisie
            # et non une intention : on ignore plutot que d'ecrire un nom vide.
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
    """Change le mot de passe, l'ancien a l'appui."""
    if not verify_password(data.ancien, user.password_hash):
        # Volontairement indistinct d'une erreur de frappe : la reponse ne dit
        # pas si le compte existe, ce qu'on sait deja, mais elle ne se prete pas
        # non plus a mesurer quoi que ce soit.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe actuel incorrect.")

    if data.nouveau == data.ancien:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Le nouveau mot de passe doit differer de l'ancien.",
        )

    probleme = validate_password(data.nouveau, email=user.email, name=user.name)
    if probleme:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, probleme)

    user.password_hash = hash_password(data.nouveau)

    # Les liens de reinitialisation en circulation sont revoques. Quelqu'un qui
    # change son mot de passe le fait souvent parce qu'il doute ; laisser vivre
    # un lien demande une heure plus tot annulerait le geste.
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
    """Change l'adresse de connexion, mot de passe a l'appui.

    La nouvelle adresse repart NON CONFIRMEE, avec un lien envoye dessus. C'est
    la seule facon de garder au drapeau son sens : sans cela, il suffirait de
    confirmer une adresse quelconque puis d'en declarer une autre pour se
    retrouver « confirme » sur une boite dont on n'a jamais prouve l'acces.
    """
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe incorrect.")

    nouvelle = str(data.email).lower()
    if nouvelle == user.email.lower():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "C'est deja ton adresse.")

    prise = db.scalar(select(models.User).where(models.User.email == nouvelle))
    if prise is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe deja avec cet e-mail.")

    user.email = nouvelle
    user.email_verified = False

    jeton = tokens.creer(db, user.id, tokens.VERIFICATION)
    sujet, texte, html = emails.confirmation_adresse(user, jeton)
    outbox.deposer(db, nouvelle, sujet, texte, html)

    db.commit()
    db.refresh(user)
    # L'ancienne adresse n'est PAS journalisee : un journal n'a pas a constituer
    # l'historique des adresses de quelqu'un.
    log.warning("adresse changee", extra={"compte": user.id, "confirmee": False})
    return user


# --------------------------------------------------------------------------
# Moyens de paiement
# --------------------------------------------------------------------------


@router.get("/paiements", response_model=list[schemas.MoyenPaiementOut])
def lister_paiements(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return db.scalars(
        select(models.PaymentMethod)
        .where(models.PaymentMethod.user_id == user.id)
        # La carte par defaut en tete : c'est celle qu'on cherche.
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
    """Enregistre une carte, sans jamais avoir vu son numero.

    Le jeton est emis ICI parce que le prestataire est simule. Dans une vraie
    integration il viendrait du navigateur, remis par l'iframe du prestataire, et
    le serveur se contenterait de le stocker - le reste du code ne changerait pas.
    """
    total = db.scalar(
        select(func.count()).select_from(models.PaymentMethod).where(
            models.PaymentMethod.user_id == user.id
        )
    )
    if total >= MAX_MOYENS_PAIEMENT:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Maximum {MAX_MOYENS_PAIEMENT} moyens de paiement enregistres.",
        )

    moyen = models.PaymentMethod(
        user_id=user.id,
        reseau=data.reseau,
        quatre_derniers=data.quatre_derniers,
        exp_mois=data.exp_mois,
        exp_annee=data.exp_annee,
        libelle=(data.libelle or "").strip() or None,
        jeton=f"pm_{secrets.token_urlsafe(24)}",
        # La toute premiere carte devient le defaut sans qu'on ait a le demander :
        # personne n'enregistre une carte pour ne pas s'en servir.
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

    # Supprimer la carte par defaut ne doit pas laisser le compte sans defaut :
    # le paiement suivant proposerait alors une liste sans selection, ce qui se
    # lit comme un oubli de l'application.
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
    """Retrouve un moyen de paiement APPARTENANT au demandeur.

    Le filtre sur `user_id` est dans la requete, pas dans un `if` qui suivrait :
    une lecture par identifiant seul, meme verifiee ensuite, laisse toujours la
    possibilite qu'une branche oublie la verification. Ici il n'y a rien a
    oublier, et un identifiant qui n'est pas le sien rend 404 - pas 403, qui
    confirmerait l'existence de la ligne.
    """
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
    """Un seul defaut par compte.

    La regle est appliquee ici plutot que par une contrainte : PostgreSQL sait
    faire un index unique partiel, SQLite non, et un index unique ordinaire sur
    (user_id, defaut) interdirait d'avoir deux cartes NON favorites. Un seul
    endroit ecrit ce drapeau, ce qui rend la regle tenable.
    """
    db.execute(
        update(models.PaymentMethod)
        .where(
            models.PaymentMethod.user_id == user_id,
            models.PaymentMethod.id != garde_id,
        )
        .values(defaut=False)
    )


# --------------------------------------------------------------------------
# Droits RGPD : portabilite (art. 20) et effacement (art. 17)
# --------------------------------------------------------------------------


@router.post("/export")
@limiter.limit("3/hour")
def exporter_mes_donnees(
    request: Request,
    data: schemas.MotDePasseIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Rend l'integralite des donnees detenues sur ce compte.

    MOT DE PASSE EXIGE, alors que la session suffirait techniquement. Un export
    rassemble en un seul fichier ce que le reste du site ne montre que par
    fragments : adresse, historique d'achat, avis. C'est precisement ce qu'un
    poste laisse ouvert quelques minutes permettrait d'emporter.

    Plafonne a trois par heure : la requete parcourt tout l'historique d'un
    compte, et rien ne justifie de le refaire toutes les secondes.
    """
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
    """Exerce le droit a l'effacement. IRREVERSIBLE.

    DEUX CONFIRMATIONS, et ce n'est pas de la ceremonie : le mot de passe prouve
    qu'on est bien la maintenant, la formule recopiee prouve qu'on a lu ce qui va
    se passer. Une seule des deux laisserait passer soit un poste laisse ouvert,
    soit un clic distrait.

    LE COMPTE N'EST PAS DETRUIT, il est vide. Ses commandes doivent rester
    rattachees pour l'obligation comptable de dix ans (Code de commerce
    L123-22), ce que le RGPD prevoit a l'article 17-3-b. Ce qui subsiste ne
    designe plus personne et sort donc du champ du reglement. Le detail est dans
    `app/rgpd.py`.
    """
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mot de passe incorrect.")

    if data.confirmation.strip().upper() != rgpd.FORMULE_CONFIRMATION:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Recopie exactement « {rgpd.FORMULE_CONFIRMATION} » pour confirmer.",
        )

    # Un administrateur qui s'efface lui-meme peut fermer la porte du
    # back-office derriere lui, sans que personne puisse la rouvrir. Le refus
    # est explicite plutot que silencieux.
    if user.is_admin:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Un compte administrateur ne peut pas s'effacer lui-meme. "
            "Retire d'abord les droits d'administration.",
        )

    bilan = rgpd.anonymiser(db, user)
    db.commit()

    return {
        "ok": True,
        "message": (
            "Ton compte a ete efface. Tes commandes sont conservees sans aucune "
            "donnee personnelle : la loi impose de garder dix ans les pieces "
            "comptables, et le RGPD le prevoit."
        ),
        "efface": bilan,
        "note_avis": (
            "Le texte de tes avis reste en ligne sous un auteur anonyme. Si l'un "
            "d'eux contient une information personnelle, ecris-nous pour le faire "
            "retirer."
        ),
    }
