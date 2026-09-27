"""Photos téléversées : une adresse par contenu, en cache pour un an. Vidéos :
une autorisation d'envoi vers R2, délivrée au back-office."""
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, videos
from ..database import get_db
from ..deps import get_admin_user, get_admin_writer
from ..ratelimit import limiter

router = APIRouter(prefix="/media", tags=["medias"])
admin_router = APIRouter(prefix="/admin/medias", tags=["admin"])


@admin_router.get("/etat")
def etat(_=Depends(get_admin_user)):
    """Le formulaire n'affiche l'envoi de vidéo que si R2 est configuré."""
    return {"videos": videos.configure(), "taille_max": videos.TAILLE_MAX, "types": sorted(videos.TYPES)}


class DemandeVideo(BaseModel):
    type: str = Field(max_length=40)
    taille: int = Field(ge=1)


@admin_router.post("/video")
@limiter.limit("20/minute")
def autoriser_une_video(request: Request, demande: DemandeVideo, _=Depends(get_admin_writer)):
    if not videos.configure():
        raise HTTPException(503, "L'envoi de vidéos n'est pas configuré sur ce serveur.")
    try:
        return videos.autorisation_d_envoi(demande.type, demande.taille)
    except videos.VideoRefusee as e:
        raise HTTPException(422, str(e)) from e

# L'adresse porte l'empreinte du contenu : elle ne désignera jamais autre chose
CACHE = "public, max-age=31536000, immutable"
# Photos publiques, lisibles de partout. Sans cet en-tête sur la réponse faite à
# une balise <img>, le navigateur gardait un an une copie non relisable, et le
# recadrage du back-office échouait sur elle : l'enregistrement ne partait pas.
EN_TETES = {"Cache-Control": CACHE, "Access-Control-Allow-Origin": "*"}


@router.get("/{empreinte}")
def photo(
    request: Request,
    empreinte: str = Path(pattern=r"^[0-9a-f]{64}$"),
    db: Session = Depends(get_db),
):
    etag = f'"{empreinte}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, **EN_TETES})
    media = db.get(models.Media, empreinte)
    if media is None:
        raise HTTPException(404, "Photo introuvable.")
    return Response(
        content=media.octets,
        media_type=media.type,
        headers={"ETag": etag, **EN_TETES},
    )
