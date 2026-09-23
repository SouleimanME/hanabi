"""Migrations : elles construisent le schéma des modèles, et corrigent les données sans toucher aux vraies.

Jouées au démarrage de l'API en production (`app/migrate.py`) : une erreur ici
se découvrait jusqu'alors au déploiement.
"""
from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models
from app.database import Base
from app.migrate import RACINE

AVANT_CORRECTION = "d4e7a9b1c2f3"


def _config(connexion) -> Config:
    # Sans alembic.ini : sa configuration des journaux couperait ceux des autres tests
    cfg = Config()
    cfg.set_main_option("script_location", str(RACINE / "migrations"))
    cfg.attributes["connection"] = connexion
    return cfg


@pytest.fixture
def moteur(tmp_path):
    moteur = create_engine(f"sqlite:///{tmp_path / 'migrations.db'}")
    yield moteur
    moteur.dispose()


def test_les_migrations_rejoignent_les_modeles(moteur):
    with moteur.begin() as cx:
        command.upgrade(_config(cx), "head")
        ecarts = compare_metadata(MigrationContext.configure(cx), Base.metadata)
    assert ecarts == [], ecarts


def test_retour_arriere_puis_de_nouveau_a_jour(moteur):
    """La migration de schéma se défait et se rejoue."""
    with moteur.begin() as cx:
        command.upgrade(_config(cx), "head")
        command.downgrade(_config(cx), "c5d8e1f2a904")
        command.upgrade(_config(cx), "head")
        ecarts = compare_metadata(MigrationContext.configure(cx), Base.metadata)
    assert ecarts == []


class TestCorrectionDuJeuDeDemonstration:
    """Première version du jeu : noms sans accents, avis au hasard et répétés."""

    POPULATION = 120
    CONDENSAT_PARTAGE = "$2b$12$condensatpartageparlapopulationgenereeXXXXXXXXXXXXXXXX"

    def _peupler(self, cx):
        maintenant = datetime.now(timezone.utc)
        with Session(bind=cx) as db:
            produit = models.Product(
                code="HNB-033", name="Baguettes Laquées", category="Tradition",
                blurb="Paire", price_cents=2200, stock=5, art="baguettes,#E0452A,#0A0605",
            )
            db.add(produit)
            db.flush()

            genere = []
            for i in range(self.POPULATION):
                genere.append(models.User(
                    name="Timothee Joly" if i % 2 else "Ines Francois",
                    email=f"genere{i}@exemple.fr",
                    password_hash=self.CONDENSAT_PARTAGE,
                    city="Orleans", addr=f"{i} place du Marche",
                ))
            vrai = models.User(
                name="Timothee Vrai", email="vrai@exemple.fr",
                password_hash="$2b$12$unvraicondensatuniqueYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY",
                city="Orleans",
            )
            db.add_all([*genere, vrai])
            db.flush()

            for i, compte in enumerate(genere[:40]):
                db.add(models.Review(
                    product_id=produit.id, user_id=compte.id, author_name="Ines F.",
                    rating=5 if i % 3 else 1,
                    text="Deuxieme commande, toujours aussi satisfait.",
                    verified=True, approved=True,
                    created_at=maintenant - timedelta(days=i),
                ))
            db.add(models.Review(
                product_id=produit.id, user_id=vrai.id, author_name="Timothee V.",
                rating=4, text="Deuxieme commande, toujours aussi satisfait.",
                verified=True, approved=True, created_at=maintenant,
            ))
            db.add(models.Review(
                product_id=produit.id, user_id=None, author_name="Léa F.", rating=5,
                text="La laque est magnifique, bien équilibrées en main.",
                verified=False, approved=True, created_at=maintenant,
            ))
            db.commit()

    @pytest.fixture
    def corrige(self, moteur):
        with moteur.begin() as cx:
            command.upgrade(_config(cx), AVANT_CORRECTION)
            self._peupler(cx)
            command.upgrade(_config(cx), "head")
        with Session(bind=moteur) as db:
            yield db

    def test_les_noms_et_les_villes_retrouvent_leurs_accents(self, corrige):
        noms = set(corrige.scalars(
            select(models.User.name).where(models.User.password_hash == self.CONDENSAT_PARTAGE)
        ))
        assert noms == {"Timothée Joly", "Inès François"}
        villes = set(corrige.scalars(
            select(models.User.city).where(models.User.password_hash == self.CONDENSAT_PARTAGE)
        ))
        assert villes == {"Orléans"}
        adresse = corrige.scalar(select(models.User.addr).where(models.User.email == "genere1@exemple.fr"))
        assert adresse == "1 place du Marché"

    def test_un_vrai_compte_n_est_pas_touche(self, corrige):
        vrai = corrige.scalar(select(models.User).where(models.User.email == "vrai@exemple.fr"))
        assert vrai.name == "Timothee Vrai"
        avis = corrige.scalar(select(models.Review).where(models.Review.user_id == vrai.id))
        assert avis.text == "Deuxieme commande, toujours aussi satisfait."

    def test_le_texte_suit_la_note_et_ne_se_repete_pas_a_la_suite(self, corrige):
        from app.demo_data import AVIS_PAR_NOTE

        avis = corrige.scalars(
            select(models.Review)
            .join(models.User, models.User.id == models.Review.user_id)
            .where(models.User.password_hash == self.CONDENSAT_PARTAGE)
            .order_by(models.Review.verified.desc(), models.Review.created_at.desc())
        ).all()
        assert len(avis) == 40
        for a in avis:
            assert a.text in AVIS_PAR_NOTE[a.rating], (a.rating, a.text)
        textes = [a.text for a in avis]
        assert all(x != y for x, y in zip(textes, textes[1:]))

    def test_l_auteur_affiche_reprend_le_nom_accentue(self, corrige):
        auteurs = set(corrige.scalars(
            select(models.Review.author_name)
            .join(models.User, models.User.id == models.Review.user_id)
            .where(models.User.password_hash == self.CONDENSAT_PARTAGE)
        ))
        assert auteurs <= {"Timothée J.", "Inès F."}

    def test_l_avis_du_catalogue_initial_est_accorde(self, corrige):
        textes = set(corrige.scalars(select(models.Review.text).where(models.Review.user_id.is_(None))))
        assert "La laque est magnifique, et elles sont bien équilibrées en main." in textes
