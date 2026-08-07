"""Marge, classement ABC, couverture de stock, tendance et correlation.

Les valeurs attendues sont calculees a la main dans chaque test : c'est la
seule facon de verifier une formule, la comparer a sa propre implementation ne
prouvant rien.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app import analytics
from app.models import Order, OrderItem, Product


@pytest.fixture
def catalogue(db_session):
    """Trois references aux profils de marge volontairement opposes."""
    produits = {
        # prix 100,00 EUR / cout 40,00 EUR -> 60 % de marge
        "forte": Product(
            code="MRG-1", name="Forte marge", category="Tradition", blurb="x",
            price_cents=10000, cost_cents=4000, stock=100, art="enso,#000,#fff",
        ),
        # prix 100,00 EUR / cout 90,00 EUR -> 10 % de marge
        "faible": Product(
            code="MRG-2", name="Faible marge", category="Tradition", blurb="x",
            price_cents=10000, cost_cents=9000, stock=100, art="wave,#000,#fff",
        ),
        # cout non renseigne
        "inconnue": Product(
            code="MRG-3", name="Cout inconnu", category="Collection", blurb="x",
            price_cents=5000, cost_cents=0, stock=10, art="fan,#000,#fff",
        ),
    }
    db_session.add_all(produits.values())
    db_session.commit()
    for p in produits.values():
        db_session.refresh(p)
    return produits


def _commande(db_session, produit, qty, numero, jours=1):
    order = Order(
        number=numero,
        email="x@test.fr",
        status="paid",
        subtotal_cents=produit.price_cents * qty,
        total_cents=produit.price_cents * qty,
        created_at=datetime.now(timezone.utc) - timedelta(days=jours),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(OrderItem(
        order_id=order.id, product_id=produit.id, name=produit.name, art=produit.art,
        unit_price_cents=produit.price_cents, unit_cost_cents=produit.cost_cents, qty=qty,
    ))
    db_session.commit()


class TestMarge:
    def test_marge_calculee_sur_les_valeurs_figees(self, db_session, catalogue):
        _commande(db_session, catalogue["forte"], qty=3, numero="M1")

        fiche = next(p for p in analytics.catalogue(db_session) if p["code"] == "MRG-1")

        # 3 x (100,00 - 40,00) = 180,00 EUR
        assert fiche["revenue_cents"] == 30000
        assert fiche["margin_cents"] == 18000
        assert fiche["margin_rate"] == 0.6
        assert fiche["unit_margin_cents"] == 6000

    def test_le_cout_fige_survit_au_changement_de_tarif(self, db_session, catalogue):
        """Une commande passee doit conserver la marge qu'elle a degagee."""
        _commande(db_session, catalogue["forte"], qty=1, numero="M2")

        catalogue["forte"].cost_cents = 9500  # le fournisseur augmente
        db_session.commit()

        fiche = next(p for p in analytics.catalogue(db_session) if p["code"] == "MRG-1")
        assert fiche["margin_cents"] == 6000  # inchangee

    def test_cout_absent_ne_donne_pas_cent_pour_cent(self, db_session, catalogue):
        """Une fiche mal remplie ne doit pas passer pour la plus rentable."""
        _commande(db_session, catalogue["inconnue"], qty=2, numero="M3")

        fiche = next(p for p in analytics.catalogue(db_session) if p["code"] == "MRG-3")

        assert fiche["revenue_cents"] == 10000
        assert fiche["margin_rate"] == 0.0
        assert fiche["unit_margin_cents"] == 0


class TestClassementABC:
    def test_la_classe_a_porte_l_essentiel_de_la_marge(self, db_session, catalogue):
        # Forte : 10 x 60,00 = 600,00 de marge. Faible : 10 x 10,00 = 100,00.
        _commande(db_session, catalogue["forte"], qty=10, numero="A1")
        _commande(db_session, catalogue["faible"], qty=10, numero="A2")

        fiches = {p["code"]: p for p in analytics.catalogue(db_session)}

        # 600 / 700 = 85,7 % : la premiere depasse deja 80 %, elle est seule en A.
        assert fiches["MRG-1"]["abc"] == "A"
        assert fiches["MRG-1"]["margin_share"] == pytest.approx(6 / 7, abs=0.001)
        assert fiches["MRG-2"]["abc"] in {"B", "C"}

    def test_part_cumulee_croissante_et_bornee(self, db_session, catalogue):
        _commande(db_session, catalogue["forte"], qty=5, numero="A3")
        _commande(db_session, catalogue["faible"], qty=5, numero="A4")

        fiches = sorted(analytics.catalogue(db_session), key=lambda p: -p["margin_cents"])
        parts = [p["cumulative_share"] for p in fiches]

        assert parts == sorted(parts)
        assert parts[-1] == pytest.approx(1.0, abs=0.001)

    def test_sans_aucune_vente(self, db_session, catalogue):
        fiches = analytics.catalogue(db_session)

        assert all(p["abc"] == "C" for p in fiches)
        assert all(p["cumulative_share"] == 0.0 for p in fiches)


class TestCouvertureDeStock:
    def test_jours_restants(self, db_session, catalogue):
        """90 unites vendues en 90 jours, 100 en stock : 100 jours de couverture."""
        _commande(db_session, catalogue["forte"], qty=90, numero="S1", jours=10)

        fiche = next(p for p in analytics.catalogue(db_session) if p["code"] == "MRG-1")

        assert fiche["daily_velocity"] == 1.0
        assert fiche["days_of_stock"] == 100.0

    def test_reference_qui_ne_se_vend_plus(self, db_session, catalogue):
        """Couverture indeterminee plutot que zero : le probleme est ailleurs."""
        fiche = next(p for p in analytics.catalogue(db_session) if p["code"] == "MRG-1")

        assert fiche["days_of_stock"] is None

    def test_les_ventes_anciennes_ne_comptent_pas(self, db_session, catalogue):
        """La couverture reflete le rythme actuel, pas la moyenne historique."""
        _commande(db_session, catalogue["forte"], qty=90, numero="S2", jours=200)

        fiche = next(p for p in analytics.catalogue(db_session) if p["code"] == "MRG-1")
        assert fiche["daily_velocity"] == 0.0

    def test_les_ruptures_sont_signalees(self, db_session, catalogue):
        catalogue["forte"].stock = 5
        db_session.commit()
        _commande(db_session, catalogue["forte"], qty=90, numero="S3", jours=10)

        rapport = analytics.profitability(analytics.catalogue(db_session))

        assert [a["name"] for a in rapport["at_risk"]] == ["Forte marge"]
        assert rapport["at_risk"][0]["days_of_stock"] == 5.0


class TestRegression:
    def test_droite_parfaite(self):
        pente, origine, r2 = analytics._regression([0.0, 10.0, 20.0, 30.0])

        assert pente == pytest.approx(10.0)
        assert origine == pytest.approx(0.0)
        assert r2 == pytest.approx(1.0)

    def test_serie_plate(self):
        pente, origine, r2 = analytics._regression([5.0, 5.0, 5.0])

        assert pente == pytest.approx(0.0)
        assert origine == pytest.approx(5.0)
        # Aucune variation a expliquer : le coefficient vaut zero par convention.
        assert r2 == 0.0

    def test_serie_bruitee(self):
        """Le coefficient doit chuter quand les points s'ecartent de la droite."""
        _, _, propre = analytics._regression([10.0, 20.0, 30.0, 40.0])
        _, _, bruite = analytics._regression([10.0, 40.0, 15.0, 35.0])

        assert propre > 0.99
        assert bruite < 0.5

    def test_un_seul_point(self):
        pente, origine, r2 = analytics._regression([42.0])

        assert (pente, origine, r2) == (0.0, 42.0, 0.0)


class TestCroissanceComposee:
    def test_doublement_en_trois_mois(self):
        # 100 -> 200 en 3 periodes : 2^(1/3) - 1 = 25,99 %
        assert analytics._cmgr(100, 200, 3) == pytest.approx(0.2599, abs=0.0001)

    def test_depuis_zero_indefini(self):
        """Aucun taux ne mene de zero a une valeur positive."""
        assert analytics._cmgr(0, 500, 6) is None

    def test_decroissance(self):
        assert analytics._cmgr(200, 100, 1) == pytest.approx(-0.5)


class TestCorrelation:
    def test_lien_parfait(self):
        assert analytics._pearson([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)

    def test_opposition_parfaite(self):
        assert analytics._pearson([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)

    def test_serie_constante_indefinie(self):
        """Sans variation, la question n'a pas de sens."""
        assert analytics._pearson([1, 2, 3], [5, 5, 5]) is None

    def test_echantillon_trop_petit(self):
        assert analytics._pearson([1, 2], [3, 4]) is None


class TestPrevision:
    def test_base_vide(self, db_session):
        res = analytics.forecast(db_session, 12, 3)

        assert res["trend"] is None
        assert res["projection"] == []

    def test_projection_prolonge_la_serie(self, db_session, catalogue):
        _commande(db_session, catalogue["forte"], qty=1, numero="P1", jours=10)

        res = analytics.forecast(db_session, 12, 3)

        assert len(res["projection"]) == 3
        # Les mois projetes suivent le dernier mois d'historique, sans trou.
        mois = [p["month"] for p in res["projection"]]
        assert mois == sorted(mois)
        assert all(p["revenue_cents"] >= 0 for p in res["projection"])

    def test_les_mois_anterieurs_a_la_boutique_sont_ecartes(self, db_session, catalogue):
        """Un mois sans vente en tete de serie n'est pas un mois faible."""
        _commande(db_session, catalogue["forte"], qty=1, numero="P2", jours=5)

        res = analytics.forecast(db_session, 12, 3)

        # L'historique retenu demarre au premier mois ayant produit du chiffre.
        assert res["history"][0]["revenue_cents"] > 0
