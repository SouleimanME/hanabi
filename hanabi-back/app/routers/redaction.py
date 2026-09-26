"""Assistant de fiche produit, pour le back-office.

Ouvert au compte de démonstration : il propose sans rien enregistrer, et son
plafond du jour est séparé de celui du marchand.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import redaction
from ..database import get_db
from ..deps import get_admin_user, is_readonly_admin
from ..models import User
from ..ratelimit import limiter

router = APIRouter(prefix="/admin/redaction", tags=["admin"])


@router.get("/etat")
def etat(db: Session = Depends(get_db), user: User = Depends(get_admin_user)):
    """Ce que le formulaire doit savoir avant d'afficher le bouton."""
    demo = is_readonly_admin(user)
    return {
        "actif": redaction.configure(),
        "plafond": redaction.plafond(demo),
        "restant": redaction.restant(db, demo),
    }


@router.post("/fiche")
@limiter.limit("6/minute")
def proposer_une_fiche(
    request: Request,
    demande: redaction.Demande,
    db: Session = Depends(get_db),
    user: User = Depends(get_admin_user),
):
    try:
        resultat, restant = redaction.proposer(db, demande, is_readonly_admin(user))
    except redaction.ErreurRedaction as e:
        raise HTTPException(e.statut_http, e.message) from e
    proposition = resultat.proposition
    return {
        "categorie": proposition.categorie,
        # Usages en lignes, comme dans le formulaire
        **{
            langue: {**fiche.model_dump(), "usages": "\n".join(fiche.usages)}
            for langue, fiche in (("fr", proposition.fr), ("en", proposition.en), ("es", proposition.es))
        },
        "photo_lue": resultat.photo_lue,
        "restant": restant,
    }
