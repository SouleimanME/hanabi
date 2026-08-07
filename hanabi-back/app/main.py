from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import settings
from .database import SessionLocal
from .demo_data import ensure_demo_dataset
from .migrate import run_migrations
from .seed import seed, ensure_admin, ensure_public_admin
from .ratelimit import limiter, SecurityHeadersMiddleware, BodySizeLimitMiddleware
from .routers import (
    auth, products, orders, reviews, promos, admin, security, newsletter, warehouse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Les migrations remplacent `create_all` : sur une base persistante, creer
    # les tables manquantes ne suffit plus, il faut aussi faire evoluer celles
    # qui existent.
    run_migrations()
    db = SessionLocal()
    try:
        seed(db)
        # Hors de `seed`, qui s'interrompt des que le catalogue existe : un
        # administrateur configure apres la premiere mise en service doit
        # quand meme etre pris en compte.
        ensure_admin(db)
        ensure_public_admin(db)
        # En dernier : la generation compte les comptes existants pour savoir
        # si elle a deja tourne, et doit donc voir les deux comptes ci-dessus.
        ensure_demo_dataset(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Hanabi API",
    description="API de la boutique Hanabi. Concue et developpee par Souleiman MECHERI.",
    version="2.0.0",
    contact={"name": "Souleiman MECHERI"},
    lifespan=lifespan,
)

# --- Securite : rate limiting global (slowapi) ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# --- Securite : limite de taille + en-tetes durcis ---
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(security.router)
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(reviews.router)
app.include_router(promos.router)
app.include_router(newsletter.router)
app.include_router(orders.router)
app.include_router(admin.router)
# Apres `admin` : meme prefixe `/admin`, mais des chemins disjoints. L'ordre
# n'a pas d'incidence ici, il suit seulement la lecture - la gestion d'abord,
# l'entrepot ensuite.
app.include_router(warehouse.router)


@app.get("/", tags=["meta"])
def root():
    """Fiche d'identite du service, servie a la racine.

    Sans cette route, la racine renvoyait le 404 par defaut de FastAPI, avec un
    laconique « Not Found ». C'est le comportement normal d'une API dont toutes
    les routes vivent ailleurs, mais quiconque ouvre l'adresse dans un
    navigateur croit a une panne. On renvoie donc de quoi s'orienter.
    """
    return {
        "service": "Hanabi API",
        "status": "ok",
        "documentation": "/docs",
        "sante": "/health",
        "boutique": "Cette adresse sert l'API. La boutique est hebergee separement.",
    }


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
