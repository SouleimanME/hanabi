"""Connexion et sessions : SQLite en local et en test, PostgreSQL en production."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def _normalise_url(raw: str) -> str:
    """`postgres://` (forme historique des hébergeurs) devient `postgresql+psycopg://`."""
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        # psycopg 3 est installé, pas psycopg2
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


DATABASE_URL = _normalise_url(settings.DATABASE_URL)
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # FastAPI utilise la connexion depuis d'autres fils
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}, future=True
    )
else:
    engine = create_engine(
        DATABASE_URL,
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

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
