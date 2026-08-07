"""
Durcissement securite de l'API.

Trois briques, toutes cote application (ce qui se code) :
  1. Rate limiting par IP (slowapi) - freine brute-force et spam de bots.
  2. Headers de securite HTTP - limite clickjacking, sniffing MIME, etc.
  3. Limite de taille des requetes - bloque les payloads abusifs.

Ce qui ne se code PAS ici et reste a activer chez l'hebergeur :
  - Protection DDoS volumetrique (Cloudflare / Railway / Render).
  - WAF et filtrage d'IP malveillantes connues.
  - HTTPS / redirection TLS (gere par le reverse proxy de l'hebergeur).
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

# Limiteur global base sur l'IP de l'appelant.
# default_limits s'applique a toutes les routes sauf surcharge explicite.
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


# Taille max d'un corps de requete. Au-dela => 413.
#
# 1 Mo etait trop juste : le back-office envoie les photos produit encodees en
# base64 dans le corps JSON, or le base64 gonfle la taille d'un tiers. Une fiche
# avec son visuel principal et trois photos de galerie depasse le mega-octet
# meme apres la reduction faite dans le navigateur, et l'enregistrement echouait
# sur « Requete trop volumineuse ».
#
# Le plafond reste une protection : il borne ce qu'une requete unique peut faire
# ingerer au serveur. La limite de debit (200 appels par minute et par IP) borne
# le reste. Configurable pour pouvoir le resserrer selon l'hebergement.
#
# Limite connue de l'approche : stocker les photos en base64 dans la base n'est
# pas ce qu'on ferait en production. On deposerait les fichiers sur un stockage
# objet et l'on ne garderait que leur URL, ce qui allegerait aussi la reponse du
# catalogue, qui transporte aujourd'hui les images de chaque produit.
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", 8_000_000))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Ajoute les en-tetes de securite recommandes a chaque reponse."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        h = response.headers
        # Empeche le navigateur de "deviner" un type de contenu (anti sniffing).
        h["X-Content-Type-Options"] = "nosniff"
        # Interdit l'affichage du site dans une iframe (anti clickjacking).
        h["X-Frame-Options"] = "DENY"
        # Ne fuite pas l'URL d'origine vers les sites tiers.
        h["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Coupe l'acces aux capteurs sensibles par defaut.
        h["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Force HTTPS cote navigateur (effet reel uniquement derriere TLS en prod).
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Politique de contenu. Cette API ne sert que du JSON : rien a charger,
        # rien a executer. Tout verrouiller supprime la surface d'attaque des
        # reponses d'erreur, qui pourraient sinon renvoyer du HTML injecte.
        # `frame-ancestors 'none'` est la version moderne de X-Frame-Options,
        # conservee au-dessus pour les navigateurs anciens.
        h["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        )
        # Empeche un navigateur d'inclure ces reponses dans un autre document.
        h["Cross-Origin-Resource-Policy"] = "same-site"
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejette les requetes dont le corps depasse MAX_BODY_BYTES."""

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > MAX_BODY_BYTES:
                    # Message actionnable : sans la limite ni la taille recue,
                    # on ne sait pas de combien on depasse ni quoi alleger.
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": (
                                f"Requete trop volumineuse : {int(cl) / 1_000_000:.1f} Mo "
                                f"pour un maximum de {MAX_BODY_BYTES / 1_000_000:.0f} Mo. "
                                "Reduis le nombre ou le poids des photos."
                            )
                        },
                    )
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "En-tete invalide."})
        return await call_next(request)
