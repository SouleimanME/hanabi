"""Connexion a la base et fabrique de sessions.

Le projet vise deux moteurs : SQLite en local et pour la suite de tests,
PostgreSQL en production. Ils n'ont pas les memes contraintes de connexion, et
c'est ici, en un seul endroit, que l'ecart est absorbe.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def _normalise_url(raw: str) -> str:
    """Ramene l'URL a la forme qu'attend SQLAlchemy 2.

    Les hebergeurs distribuent encore des chaines commencant par `postgres://`,
    forme historique que SQLAlchemy 2 ne reconnait plus : il faut `postgresql://`,
    eventuellement suffixe du pilote. On corrige plutot que de laisser un
    `Can't load plugin` incomprehensible au demarrage.
    """
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        # Pilote explicite : sans lui, SQLAlchemy cherche psycopg2, absent des
        # dependances. C'est psycopg 3 qui est installe.
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


DATABASE_URL = _normalise_url(settings.DATABASE_URL)
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # SQLite refuse par defaut qu'une connexion soit utilisee par un autre fil
    # que celui qui l'a ouverte, ce que fait FastAPI.
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}, future=True
    )
else:
    engine = create_engine(
        DATABASE_URL,
        future=True,
        # `pool_pre_ping` teste la connexion avant de la preter. Sur une base
        # serverless qui se met en veille apres quelques minutes d'inactivite,
        # les connexions du pool sont coupees cote serveur sans que le client en
        # soit averti : sans ce test, la premiere requete apres une pause echoue
        # sur une connexion morte. C'est le reglage sans lequel le site parait
        # cassé une fois sur deux.
        pool_pre_ping=True,
        # Recycle avant que l'hebergeur ne coupe de lui-meme.
        pool_recycle=280,
        # Le plan gratuit plafonne le nombre de connexions simultanees, et un
        # service web a un seul processus n'a pas besoin de davantage.
        pool_size=5,
        max_overflow=5,
        # Ne pas attendre indefiniment qu'une connexion se libere : mieux vaut
        # une erreur franche qu'une requete suspendue.
        pool_timeout=10,
        connect_args={
            "connect_timeout": 10,
            # Fuseau force a UTC pour la session. Les regroupements mensuels du
            # tableau de bord decoupent une date en texte : si le serveur
            # repondait dans un autre fuseau, une commande de fin de mois
            # basculerait dans le mois suivant, et les totaux ne tomberaient
            # jamais tout a fait juste.
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
