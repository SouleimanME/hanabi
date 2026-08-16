import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from . import models, outbox
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
    exploitation, compte,
)

log = logging.getLogger("hanabi.demarrage")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # En premier : tout ce qui suit doit deja etre journalise au bon format.
    configurer_journaux()

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
        # Deux tables qui ne font que croitre si personne ne les taille : des
        # traces de requetes et des jetons morts. La purge au demarrage suffit
        # ici - le service redemarre a chaque deploiement, et aucune des deux
        # n'atteint un volume genant entre-temps. Une tache periodique serait la
        # bonne reponse sur un service qui tourne des mois sans redemarrer.
        oubliees = purger_idempotence(db)
        if oubliees:
            log.info("cles d'idempotence purgees", extra={"lignes": oubliees})
        jetons_morts = purger_jetons(db)
        if jetons_morts:
            log.info("jetons expires purges", extra={"lignes": jetons_morts})
    finally:
        db.close()

    # Ouvrier de remise des courriels. A intervalle nul, il ne demarre pas :
    # c'est ce que fait la suite de tests, qui declenche la remise elle-meme
    # pour rester deterministe.
    arret = asyncio.Event()
    tache = None
    if settings.OUTBOX_INTERVALLE_SECONDES > 0:
        tache = asyncio.create_task(outbox.ouvrier(arret))

    yield

    if tache is not None:
        arret.set()
        try:
            # Borne l'attente : un ouvrier bloque sur un relais muet ne doit pas
            # retenir l'extinction du service, que l'hebergeur finirait par tuer.
            await asyncio.wait_for(tache, timeout=10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            tache.cancel()


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

# --- Observabilite : identifiant de requete, duree, journal structure ---
#
# Ajoute EN DERNIER, donc execute EN PREMIER : Starlette empile les
# intermediaires et parcourt la pile a l'envers. C'est ce qu'on veut - une
# requete rejetee par la limitation de debit ou par la taille du corps doit
# quand meme porter un identifiant et apparaitre dans le journal, faute de quoi
# les seules requetes invisibles seraient precisement celles qu'on refuse.
app.add_middleware(RequestContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(security.router)
app.include_router(auth.router)
# Apres `auth` : `auth` porte l'entree dans le compte (inscription, connexion,
# recuperation), `compte` ce qu'on y fait une fois dedans.
app.include_router(compte.router)
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
# Meme prefixe `/admin`, chemins disjoints la encore : l'etat d'exploitation
# (file de courriels, commandes a rapprocher) vit sous `/admin/exploitation`.
app.include_router(exploitation.router)


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
def health(response: Response, db: Session = Depends(get_db)):
    """Etat du service, verifie plutot que declare.

    L'ancienne version rendait `{"status": "ok"}` en dur. Une sonde de ce genre
    ne dit qu'une chose - le processus Python repond - et c'est rarement ce qui
    tombe. Une base injoignable, un pool epuise ou une base en veille laissaient
    la sonde au vert pendant que chaque page renvoyait une erreur : la
    surveillance ne redemarrait rien, et personne n'etait prevenu.

    On execute donc un aller-retour reel jusqu'a la base. Un echec rend 503, ce
    qui est le code que les hebergeurs et les repartiteurs de charge savent lire
    pour retirer une instance du service.

    La session vient de la meme injection que toutes les autres routes. Une
    version anterieure ouvrait la sienne avec `SessionLocal()`, ce qui la
    faisait interroger une base differente de celle du reste de la requete -
    invisible en production, ou il n'y en a qu'une, mais la sonde devenait
    intestable et ne prouvait plus rien de ce qu'elle affirmait. Ouvrir une
    session ne se connecte pas : c'est le `SELECT 1` ci-dessous qui etablit
    reellement le lien, donc l'echec reste attrape ici et rendu en 503.
    """
    etat = {"status": "ok", "base": "ok"}
    try:
        db.execute(text("SELECT 1"))
    except Exception as erreur:  # noqa: BLE001 - toute panne de base vaut indisponibilite
        log.exception("sonde de sante : base injoignable")
        etat["status"] = "degrade"
        # Le detail de l'erreur reste dans le journal : une sonde est souvent
        # publique, et le message d'un pilote de base y expose volontiers le
        # nom d'hote et le port.
        etat["base"] = "injoignable"
        etat["erreur"] = type(erreur).__name__
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return etat

    # File de courriels. Une file qui s'allonge est le symptome le plus fidele
    # d'un relais en panne, et elle ne se voit nulle part ailleurs : l'ouvrier
    # echoue en silence par construction, puisque son role est justement
    # d'absorber les pannes sans les faire remonter au visiteur. Sans cette
    # ligne, on decouvrirait le probleme par un client qui n'a pas recu sa
    # confirmation.
    #
    # En attente n'est PAS une anomalie : c'est l'etat normal d'un message entre
    # son ecriture et sa remise, quelques secondes plus tard. Seuls les
    # ABANDONS - cinq tentatives epuisees - degradent la sonde.
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
            # Pas de 503 : le service repond, prend des commandes et sert des
            # pages. Seule la remise du courrier est en defaut. Retirer
            # l'instance du service aggraverait une panne partielle.
    except Exception:  # noqa: BLE001 - la table peut manquer avant migration
        log.exception("sonde de sante : file de courriels illisible")
        etat["courriels"] = "illisible"
    return etat
