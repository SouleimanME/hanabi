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


AVANT_BASCULE = "e8b2c4d6f1a3"

# Catalogue de démonstration d'origine : code, nom, catégorie, blason
ANCIEN_CATALOGUE = [
    ("HNB-014", "Collier Maneki-neko", "Compagnons", "suzu,#E0452A,#0A0605"),
    ("HNB-021", "Lampe Torii LED", "Collection", "torii,#E0452A,#0A0605"),
    ("HNB-008", "Bandana Sushi", "Compagnons", "bandana,#0A0605,#D8452B"),
    ("HNB-015", "Gamelle Sakura", "Compagnons", "sakura,#E0452A,#EFE7D6"),
    ("HNB-033", "Baguettes Laquées", "Tradition", "baguettes,#E0452A,#0A0605"),
    ("HNB-037", "Éventail Sensu", "Tradition", "fan,#0A0605,#D8452B"),
    ("HNB-041", "Bol à Ramen", "Tradition", "bol,#0A0605,#D8452B"),
    ("HNB-009", "Coussin Futon Néko", "Compagnons", "futon,#0A0605,#EFE7D6"),
    ("HNB-052", "Figurine Kitsune", "Collection", "kitsune,#E0452A,#0A0605"),
    ("HNB-045", "Tenugui Seigaiha", "Tradition", "seigaiha,#0A0605,#A83019"),
    ("HNB-026", "Lampe Lune", "Collection", "moon,#0A0605,#EFE7D6"),
    ("HNB-018", "Maneki-neko Doré", "Collection", "neko,#0A0605,#D8452B"),
]
PHOTO_DU_MARCHAND = "https://exemple.fr/ma-lampe-lune.jpg"
CONDENSAT_GENERE = "$2b$12$condensatpartageparlapopulationgenereeZZZZZZZZZZZZZZZZ"


class TestBasculeVersFigurinesEtDecoration:
    """Le catalogue de démonstration ne garde que figurines et décoration."""

    def _ancien_catalogue(self, cx):
        with Session(bind=cx) as db:
            for code, nom, categorie, art in ANCIEN_CATALOGUE:
                db.add(models.Product(
                    code=code, name=nom, category=categorie, blurb="x",
                    price_cents=1000, stock=5, art=art, images="[]",
                ))
            db.flush()
            # La lampe lune a déjà reçu une vraie photo du marchand
            lune = db.scalar(select(models.Product).where(models.Product.code == "HNB-026"))
            lune.art = PHOTO_DU_MARCHAND
            # Une commande passée sur le collier, qui doit rester lisible
            collier = db.scalar(select(models.Product).where(models.Product.code == "HNB-014"))
            client = models.User(name="Client", email="client@exemple.fr", password_hash="x")
            db.add(client)
            db.flush()
            commande = models.Order(
                number="HNB-TEST-1", user_id=client.id, email=client.email,
                subtotal_cents=1000, discount_cents=0, shipping_cents=0, total_cents=1000,
            )
            db.add(commande)
            db.flush()
            db.add(models.OrderItem(
                order_id=commande.id, product_id=collier.id, name=collier.name,
                art=collier.art, qty=1, unit_price_cents=1000,
            ))
            # Population générée : une commande, un avis et une vue sur le collier
            generes = [
                models.User(name=f"Généré {i}", email=f"g{i}@exemple.fr", password_hash=CONDENSAT_GENERE)
                for i in range(120)
            ]
            db.add_all(generes)
            db.flush()
            achat = models.Order(
                number="HNB-GEN-1", user_id=generes[0].id, email=generes[0].email,
                subtotal_cents=2400, total_cents=2400,
            )
            db.add(achat)
            db.flush()
            db.add(models.OrderItem(
                order_id=achat.id, product_id=collier.id, name=collier.name,
                art=collier.art, qty=1, unit_price_cents=2400,
            ))
            db.add(models.Review(
                product_id=collier.id, user_id=generes[0].id, author_name="Généré G.",
                rating=5, text="Parfait.", verified=True, approved=True,
            ))
            db.add(models.ProductView(product_id=collier.id, user_id=generes[1].id))
            db.commit()

    @pytest.fixture
    def bascule(self, moteur):
        with moteur.begin() as cx:
            command.upgrade(_config(cx), AVANT_BASCULE)
            self._ancien_catalogue(cx)
            command.upgrade(_config(cx), "head")
        with Session(bind=moteur) as db:
            yield db

    def _vitrine(self, db):
        return {p.code: p for p in db.scalars(select(models.Product).where(models.Product.active.is_(True)))}

    def test_la_vitrine_compte_douze_objets_des_trois_categories(self, bascule):
        from app.routers.admin import CATEGORIES

        vitrine = self._vitrine(bascule)
        assert len(vitrine) == 12
        assert {p.category for p in vitrine.values()} == set(CATEGORIES)

    def test_les_series_retirees_restent_en_base_desactivees(self, bascule):
        retires = {"HNB-014", "HNB-008", "HNB-015", "HNB-009", "HNB-033", "HNB-041", "HNB-045"}
        lignes = bascule.scalars(select(models.Product).where(models.Product.code.in_(retires))).all()
        assert {p.code for p in lignes} == retires
        assert not any(p.active for p in lignes)

    def test_les_objets_gardes_changent_de_categorie_et_passent_en_photo(self, bascule):
        vitrine = self._vitrine(bascule)
        assert vitrine["HNB-021"].category == "Luminaires"
        assert vitrine["HNB-037"].category == "Décoration"
        assert vitrine["HNB-052"].category == "Figurines"
        assert vitrine["HNB-021"].art.startswith("https://images.unsplash.com/")

    def test_la_photo_du_marchand_n_est_pas_ecrasee(self, bascule):
        assert self._vitrine(bascule)["HNB-026"].art == PHOTO_DU_MARCHAND

    def test_l_historique_genere_passe_a_l_equivalent(self, bascule):
        masque = self._vitrine(bascule)["HNB-061"]
        ligne = bascule.scalar(
            select(models.OrderItem).join(models.Order).where(models.Order.number == "HNB-GEN-1")
        )
        assert (ligne.product_id, ligne.name) == (masque.id, "Masque Kitsune")
        assert ligne.art.startswith("https://images.unsplash.com/")
        assert bascule.scalar(select(models.Review.product_id).where(models.Review.text == "Parfait.")) == masque.id
        assert bascule.scalar(select(models.ProductView.product_id)) == masque.id

    def test_la_commande_d_un_vrai_client_reste_sur_le_collier(self, bascule):
        ligne = bascule.scalar(
            select(models.OrderItem).join(models.Order).where(models.Order.number == "HNB-TEST-1")
        )
        collier = bascule.scalar(select(models.Product).where(models.Product.code == "HNB-014"))
        assert (ligne.product_id, ligne.name) == (collier.id, "Collier Maneki-neko")

    def test_une_base_neuve_reste_vide_pour_seed(self, moteur):
        with moteur.begin() as cx:
            command.upgrade(_config(cx), "head")
        with Session(bind=moteur) as db:
            assert db.scalar(select(models.Product)) is None

    def test_un_nouvel_objet_deja_consulte_revient_apres_aller_retour(self, moteur):
        """Une vue anonyme le garde en base au retour arrière ; la mise à jour suivante le réactive."""
        with moteur.begin() as cx:
            command.upgrade(_config(cx), AVANT_BASCULE)
            self._ancien_catalogue(cx)
            command.upgrade(_config(cx), "head")
            with Session(bind=cx) as db:
                hannya = db.scalar(select(models.Product).where(models.Product.code == "HNB-064"))
                db.add(models.ProductView(product_id=hannya.id, user_id=None))
                db.commit()
            command.downgrade(_config(cx), AVANT_BASCULE)
            command.upgrade(_config(cx), "head")
        with Session(bind=moteur) as db:
            assert len(self._vitrine(db)) == 12

    def test_le_retour_arriere_rend_l_ancienne_vitrine(self, moteur):
        with moteur.begin() as cx:
            command.upgrade(_config(cx), AVANT_BASCULE)
            self._ancien_catalogue(cx)
            command.upgrade(_config(cx), "head")
            command.downgrade(_config(cx), AVANT_BASCULE)
        with Session(bind=moteur) as db:
            vitrine = self._vitrine(db)
            assert set(vitrine) == {code for code, *_ in ANCIEN_CATALOGUE}
            assert vitrine["HNB-021"].category == "Collection"
            assert vitrine["HNB-021"].art == "torii,#E0452A,#0A0605"
            assert vitrine["HNB-026"].art == PHOTO_DU_MARCHAND
            ligne = db.scalar(
                select(models.OrderItem).join(models.Order).where(models.Order.number == "HNB-GEN-1")
            )
            assert (ligne.product_id, ligne.name) == (vitrine["HNB-014"].id, "Collier Maneki-neko")
            assert db.scalar(select(models.Product).where(models.Product.code == "HNB-061")) is None
