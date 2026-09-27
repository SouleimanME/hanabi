"""Vidéos des fiches produit, déposées sur Cloudflare R2.

Une vidéo pèse des dizaines de mégaoctets : dans la base, elle épuiserait
l'offre gratuite de Neon, et servie par l'API elle ne se lirait pas bien
(Safari exige des requêtes par plages). Elle part donc du navigateur
directement vers R2, avec une autorisation signée que l'API délivre au
back-office : valable quinze minutes, pour un seul fichier et un seul type.
La fiche ne garde que l'adresse publique de la vidéo.

La signature suit AWS Signature Version 4, que R2 accepte ; elle est écrite
ici plutôt que tirée d'une bibliothèque, et vérifiée contre le vecteur de
test publié par AWS (tests/test_videos.py).
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from .config import settings

TYPES = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov"}
# Une présentation d'objet dure moins d'une minute
TAILLE_MAX = 200 * 1024 * 1024
VALIDITE_SECONDES = 15 * 60


def configure() -> bool:
    return all((
        settings.R2_ACCOUNT_ID, settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY,
        settings.R2_BUCKET, settings.R2_PUBLIC_URL,
    ))


def _hmac(cle: bytes, texte: str) -> bytes:
    return hmac.new(cle, texte.encode(), hashlib.sha256).digest()


def _echapper(texte: str, garder: str = "-_.~") -> str:
    return quote(texte, safe=garder)


def presigner(
    methode: str,
    hote: str,
    chemin: str,
    cle_id: str,
    secret: str,
    region: str,
    maintenant: datetime,
    duree: int,
    entetes: dict[str, str] | None = None,
) -> str:
    """Adresse présignée SigV4, en paramètres de requête (service s3)."""
    entetes = {"host": hote, **{k.lower(): v.strip() for k, v in (entetes or {}).items()}}
    signes = ";".join(sorted(entetes))
    date = maintenant.strftime("%Y%m%dT%H%M%SZ")
    jour = maintenant.strftime("%Y%m%d")
    portee = f"{jour}/{region}/s3/aws4_request"
    parametres = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{cle_id}/{portee}",
        "X-Amz-Date": date,
        "X-Amz-Expires": str(duree),
        "X-Amz-SignedHeaders": signes,
    }
    requete = "&".join(f"{_echapper(k)}={_echapper(v)}" for k, v in sorted(parametres.items()))
    canonique = "\n".join([
        methode,
        _echapper(chemin, "/-_.~"),
        requete,
        "".join(f"{k}:{entetes[k]}\n" for k in sorted(entetes)),
        signes,
        "UNSIGNED-PAYLOAD",
    ])
    a_signer = "\n".join([
        "AWS4-HMAC-SHA256", date, portee, hashlib.sha256(canonique.encode()).hexdigest(),
    ])
    cle = _hmac(_hmac(_hmac(_hmac(f"AWS4{secret}".encode(), jour), region), "s3"), "aws4_request")
    signature = hmac.new(cle, a_signer.encode(), hashlib.sha256).hexdigest()
    return f"https://{hote}{_echapper(chemin, '/-_.~')}?{requete}&X-Amz-Signature={signature}"


class VideoRefusee(ValueError):
    pass


def autorisation_d_envoi(type_mime: str, taille: int) -> dict:
    """Ce qu'il faut au navigateur pour déposer une vidéo, et son adresse publique."""
    extension = TYPES.get(type_mime)
    if extension is None:
        raise VideoRefusee("Vidéo attendue en MP4, WebM ou MOV.")
    if not 0 < taille <= TAILLE_MAX:
        raise VideoRefusee(f"Vidéo de {TAILLE_MAX // (1024 * 1024)} Mo au plus.")
    cle = f"videos/{uuid.uuid4().hex}.{extension}"
    hote = f"{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    envoi = presigner(
        "PUT", hote, f"/{settings.R2_BUCKET}/{cle}",
        settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY, "auto",
        datetime.now(timezone.utc), VALIDITE_SECONDES,
        # Le type est signé : le fichier déposé ne peut pas en changer
        {"content-type": type_mime},
    )
    return {
        "envoi": envoi,
        "entetes": {"Content-Type": type_mime},
        "url": f"{settings.R2_PUBLIC_URL.rstrip('/')}/{cle}",
    }
