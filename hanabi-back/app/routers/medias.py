"""Photos téléversées : une adresse par contenu, en cache pour un an."""
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/media", tags=["medias"])

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
