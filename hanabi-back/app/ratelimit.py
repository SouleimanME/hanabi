"""Protections applicatives de l'API : limitation de débit, en-têtes de sécurité, taille du corps.

Restent du ressort de l'hébergeur : protection DDoS, WAF, terminaison TLS.
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

# Limite par IP, surchargée route par route
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


# Corps maximal (413 au-delà). Les photos produit arrivent en base64 dans le JSON,
# d'où 8 Mo ; un stockage objet permettrait de redescendre.
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", 8_000_000))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """En-têtes de sécurité sur chaque réponse."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        h = response.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "strict-origin-when-cross-origin"
        h["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # L'API ne sert que du JSON : rien à charger ni à exécuter
        h["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        )
        h["Cross-Origin-Resource-Policy"] = "same-site"
        return response


def _message_413(recu: int) -> str:
    """Indique la taille reçue et la limite."""
    return (
        f"Requête trop volumineuse : {recu / 1_000_000:.1f} Mo "
        f"pour un maximum de {MAX_BODY_BYTES / 1_000_000:.0f} Mo. "
        "Réduis le nombre ou le poids des photos."
    )


class _CorpsTropGros(Exception):
    """Levée dès que le corps reçu franchit le plafond."""


class BodySizeLimitMiddleware:
    """Rejette les corps au-delà de MAX_BODY_BYTES.

    Compte les octets réellement reçus : `Content-Length` manque en
    `Transfer-Encoding: chunked`. L'en-tête reste vérifié d'abord pour refuser
    tôt. Intermédiaire ASGI, seul moyen de lire le flux entrant.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        entetes = dict(scope.get("headers") or [])
        annonce = entetes.get(b"content-length")
        if annonce is not None:
            try:
                taille = int(annonce)
            except ValueError:
                await self._repond(send, 400, "En-tête invalide.")
                return
            if taille > MAX_BODY_BYTES:
                await self._repond(send, 413, _message_413(taille))
                return

        recu = 0

        async def receive_borne():
            nonlocal recu
            message = await receive()
            if message.get("type") == "http.request":
                recu += len(message.get("body", b""))
                if recu > MAX_BODY_BYTES:
                    raise _CorpsTropGros(recu)
            return message

        commencee = False

        async def send_suivi(message):
            nonlocal commencee
            if message.get("type") == "http.response.start":
                commencee = True
            await send(message)

        try:
            await self.app(scope, receive_borne, send_suivi)
        except _CorpsTropGros as trop:
            # Réponse déjà partie : impossible de la réécrire
            if commencee:
                raise
            await self._repond(send, 413, _message_413(trop.args[0]))

    @staticmethod
    async def _repond(send, code: int, detail: str) -> None:
        reponse = JSONResponse(status_code=code, content={"detail": detail})
        await send({
            "type": "http.response.start",
            "status": code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(reponse.body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": reponse.body})
