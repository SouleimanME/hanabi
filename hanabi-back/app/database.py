"""Connexion et sessions : SQLite en local et en test, PostgreSQL en production."""
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# Base joignable sans quitter la machine : socket local ou boucle locale
HOTES_LOCAUX = {None, "", "localhost", "127.0.0.1", "::1"}


def normalise_url(raw: str) -> str:
    """`postgres://` (forme historique des hébergeurs) devient `postgresql+psycopg://`."""
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        # psycopg 3 est installé, pas psycopg2
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


def base_locale(url: str | URL) -> bool:
    url = make_url(url)
    return url.get_backend_name() == "sqlite" or url.host in HOTES_LOCAUX


def creer_moteur(url: str):
    """Moteur de l'application ; la suite de tests sur PostgreSQL reprend ses réglages."""
    if url.startswith("sqlite"):
        # FastAPI utilise la connexion depuis d'autres fils
        return create_engine(url, connect_args={"check_same_thread": False}, future=True)
    return create_engine(
        url,
        future=True,
        # Neon coupe les connexions en veille sans prévenir le client
        pool_pre_ping=True,
        pool_recycle=280,
        # Plafond de connexions du plan gratuit, un seul processus web
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        connect_args={
            "connect_timeout": 10,
            # UTC en session : les regroupements mensuels découpent la date en texte
            "options": "-c timezone=utc",
        },
    )


DATABASE_URL = normalise_url(settings.DATABASE_URL)
engine = creer_moteur(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
