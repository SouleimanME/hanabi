"""Délivrance des défis anti-robots."""
from fastapi import APIRouter, HTTPException, Request, status

from ..antibot import Challenge, issue_challenge
from ..ratelimit import limiter

router = APIRouter(prefix="/security", tags=["security"])

# Un défi ne vaut que pour l'usage demandé
ALLOWED_PURPOSES = {"register", "login", "notify", "review", "subscribe"}


@router.get("/challenge", response_model=Challenge)
@limiter.limit("40/minute")
def challenge(request: Request, purpose: str):
    if purpose not in ALLOWED_PURPOSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Usage inconnu.")
    return issue_challenge(purpose)
