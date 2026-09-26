import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import models, outbox, recherche
from .audience import detacher_consultations_anciennes
from .config import settings
from .database import SessionLocal, get_db
from .demo_data import ensure_demo_dataset
from .idempotency import purger as purger_idempotence
from .migrate import run_migrations
from .tokens import purger as purger_jetons
from .observability import RequestContextMiddleware, configurer_journaux
from .seed import seed, ensure_admin, ensure_public_admin
from .ratelimit import limiter, SecurityHeadersMiddleware, BodySizeLimitMiddleware
from .routers import (
    auth, products, orders, reviews, promos, admin, security, newsletter, warehouse,
    exploitation, compte, redaction,
)

log = logging.getLogger("hanabi.demarrage")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configurer_journaux()

    run_migrations()
    db = SessionLocal()
    try:
        seed(db)
        # Hors de `seed`, qui s'arrête dès que le catalogue existe
        ensure_admin(db)
        ensure_public_admin(db)
        # Après les comptes ci-dessus : la génération compte les comptes existants
        ensure_demo_dataset(db)
        # Purge au démarrage, suffisante puisque chaque déploiement redémarre
        oubliees = purger_idempotence(db)
        if oubliees:
            log.info("cles d'idempotence purgees", extra={"lignes": oubliees})
        jetons_morts = purger_jetons(db)
        if jetons_morts:
            log.info("jetons expires purges", extra={"lignes": jetons_morts})
        detachees = detacher_consultations_anciennes(db)
        if detachees:
            log.info("consultations detachees de leur compte", extra={"lignes": detachees})
    finally:
        db.close()

    # Le modèle de recherche se charge en arrière-plan : le premier visiteur
    # n'attend pas, il a la recherche par le texte d'ici là
    if settings.RECHERCHE_SEMANTIQUE:
        threading.Thread(
            target=recherche.prechauffer, args=(SessionLocal,), name="recherche", daemon=True
        ).start()

    # Remise des courriels ; à intervalle nul (tests), rien ne démarre
    arret = asyncio.Event()
    tache = None
    if settings.OUTBOX_INTERVALLE_SECONDES > 0:
        tache = asyncio.create_task(outbox.ouvrier(arret))

    yield

    if tache is not None:
        arret.set()
        try:
            # Un relais muet ne doit pas retenir l'extinction
            await asyncio.wait_for(tache, timeout=10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            tache.cancel()


app = FastAPI(
    title="Hanabi API",
    description="API de la boutique Hanabi. Conçue et développée par Souleiman MECHERI.",
    version="2.0.0",
    contact={"name": "Souleiman MECHERI"},
    lifespan=lifespan,
    # Documentation fermée en production : elle publierait le plan complet des routes
    docs_url=None if settings.is_prod else "/docs",
    redoc_url=None if settings.is_prod else "/redoc",
    openapi_url=None if settings.is_prod else "/openapi.json",
)

# --- Limitation de débit globale ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# --- Taille du corps et en-têtes de sécurité ---
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# --- Identifiant de requête et journal ---
# Ajouté après les protections, donc exécuté avant elles : les requêtes
# qu'elles refusent sont journalisées aussi.
app.add_middleware(RequestContextMiddleware)

# Le plus extérieur : toute réponse, même d'erreur, porte les en-têtes CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(security.router)
app.include_router(auth.router)
app.include_router(compte.router)
app.include_router(products.router)
app.include_router(reviews.router)
app.include_router(promos.router)
app.include_router(newsletter.router)
app.include_router(orders.router)
# admin, warehouse, exploitation et redaction partagent le préfixe /admin, sur des chemins disjoints
app.include_router(admin.router)
app.include_router(warehouse.router)
app.include_router(exploitation.router)
app.include_router(redaction.router)


@app.get("/", tags=["meta"])
def root():
    """Fiche du service à la racine, au lieu d'un 404 déroutant dans un navigateur."""
    fiche = {
        "service": "Hanabi API",
        "status": "ok",
        "sante": "/health",
        "boutique": "Cette adresse sert l'API. La boutique est hébergée séparément.",
    }
    if not settings.is_prod:
        fiche["documentation"] = "/docs"
    return fiche


@app.get("/health", tags=["meta"])
def health(response: Response, db: Session = Depends(get_db)):
    """État vérifié du service.

    Aller-retour réel jusqu'à la base (503 si elle ne répond pas) et état de la
    file de courriels. La session vient de `get_db`, comme partout, pour que la
    sonde se teste.
    """
    etat = {"status": "ok", "base": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - toute panne de base vaut indisponibilite
        # Détail dans le journal seulement : la sonde est publique
        log.exception("sonde de sante : base injoignable")
        etat["status"] = "degrade"
        etat["base"] = "injoignable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return etat

    # Des messages en attente sont normaux ; seuls les abandons dégradent la
    # sonde, sans 503 puisque le reste du service fonctionne.
    try:
        etat["courriels"] = {
            "en_attente": db.scalar(
                select(func.count()).select_from(models.OutboxEmail).where(
                    models.OutboxEmail.statut == "en_attente"
                )
            ),
            "abandonnes": db.scalar(
                select(func.count()).select_from(models.OutboxEmail).where(
                    models.OutboxEmail.statut == "abandonne"
                )
            ),
        }
        if etat["courriels"]["abandonnes"]:
            etat["status"] = "degrade"
            log.warning("courriels abandonnes en file", extra=etat["courriels"])
    except Exception:  # noqa: BLE001 - la table peut manquer avant migration
        log.exception("sonde de sante : file de courriels illisible")
        etat["courriels"] = "illisible"
    return etat
