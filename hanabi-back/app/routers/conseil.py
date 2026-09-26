"""Conseiller cadeau de la boutique.

Formulaire public : barrières anti-robots, limite par adresse IP et plafond
du jour en base. Le texte de la demande part chez le fournisseur pour y
répondre et n'est conservé nulle part.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import conseil, fournisseur, plongement
from ..antibot import AntiBotFields
from ..antibot import verify as verify_antibot
from ..config import settings
from ..database import get_db
from ..ratelimit import limiter
from .products import _ratings_map, _to_out

router = APIRouter(prefix="/conseil", tags=["conseil"])


class DemandeConseil(BaseModel):
    demande: str = Field(min_length=3, max_length=400)
    lang: Literal["fr", "en", "es"] = "fr"
    antibot: AntiBotFields


@router.get("/etat")
def etat():
    """La boutique n'affiche le conseiller que s'il peut répondre."""
    return {"actif": fournisseur.configure()}


@router.post("")
@limiter.limit("3/minute;20/day")
def conseiller(request: Request, data: DemandeConseil, db: Session = Depends(get_db)):
    verify_antibot(data.antibot, "conseil")
    encodeur = plongement.encodeur() if settings.RECHERCHE_SEMANTIQUE else None
    try:
        resultat = conseil.conseiller(db, data.demande.strip(), data.lang, encodeur)
    except fournisseur.ErreurFournisseur as e:
        raise HTTPException(e.statut_http, e.message) from e
    notes = _ratings_map(db, [p.id for p, _ in resultat.choix])
    return {
        "message": resultat.message,
        "vide": resultat.vide,
        "choix": [
            {"produit": _to_out(p, notes.get(p.id, (0.0, 0)), data.lang), "raison": raison}
            for p, raison in resultat.choix
        ],
    }
