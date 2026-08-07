"""Cohortes, segmentation RFM et regles d'association.

Ces analyses se pretent mal a un test « sur donnees reelles » : leur resultat
depend du jeu de donnees. On verifie donc leurs proprietes structurelles et
leurs cas limites, plus quelques scenarios construits a la main dont on connait
la reponse a l'avance.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app import analytics
from app.models import Order, OrderItem, ProductView, User
from app.security import hash_password


def _mois(offset: int) -> str:
    """Cle « AAAA-MM » decalee de `offset` mois par rapport a aujourd'hui."""
    return analytics._last_months(abs(offset) + 1)[0] if offset <= 0 else ""


@pytest.fixture
def acheteurs(db_session, product):
    """Construit un historique connu : trois clients aux profils distincts.

    - `fidele` : six commandes, la derniere hier ;
    - `unique` : une seule commande, hier ;
    - `perdu`  : deux commandes, la derniere il y a plus d'un an.
    """
    maintenant = datetime.now(timezone.utc)
    profils = {
        "fidele": (6, 1),
        "unique": (1, 1),
        "perdu": (2, 400),
    }
    crees = {}
    numero = 1000
    for nom, (commandes, anciennete) in profils.items():
        user = User(
            name=nom.capitalize(),
            email=f"{nom}@test.fr",
            password_hash=hash_password("MotDePasse1!"),
            created_at=maintenant - timedelta(days=500),
        )
        db_session.add(user)
        db_session.flush()
        crees[nom] = user

        for i in range(commandes):
            numero += 1
            passee_le = maintenant - timedelta(days=anciennete + i * 30)
            order = Order(
                number=f"ATL{numero}",
                user_id=user.id,
                email=user.email,
                status="paid",
                subtotal_cents=2000,
                total_cents=2000,
                created_at=passee_le,
            )
            db_session.add(order)
            db_session.flush()
            db_session.add(OrderItem(
                order_id=order.id, product_id=product.id, name=product.name,
                art=product.art, unit_price_cents=2000, qty=1,
            ))
    db_session.commit()
    return crees


def _segments_par_email(db_session) -> dict[str, str]:
    """Segment attribue a chaque client, indexe par adresse.

    `rfm_segments` ne renvoie que les trois meilleurs clients par segment ; on
    rejoue donc le classement sur l'ensemble pour pouvoir interroger un compte
    precis.
    """
    resultat = analytics.rfm_segments(db_session)
    par_email = {e["email"]: e["segment"] for e in resultat["examples"]}
    return par_email


@pytest.fixture
def population(db_session, product):
    """Une clientele assez fournie pour que les quintiles separent quelque chose.

    Les scores RFM sont des rangs : ils n'ont de sens que compares a une
    population. Quatre profils sont poses volontairement aux extremes, le reste
    remplit la distribution entre les deux.
    """
    maintenant = datetime.now(timezone.utc)
    numero = [5000]

    def acheteur(email, commandes, recence_jours, montant_cents):
        user = User(
            name=email.split("@")[0],
            email=email,
            password_hash=hash_password("MotDePasse1!"),
            created_at=maintenant - timedelta(days=600),
        )
        db_session.add(user)
        db_session.flush()
        for i in range(commandes):
            numero[0] += 1
            order = Order(
                number=f"ATL{numero[0]}",
                user_id=user.id,
                email=email,
                status="paid",
                subtotal_cents=montant_cents,
                total_cents=montant_cents,
                created_at=maintenant - timedelta(days=recence_jours + i * 25),
            )
            db_session.add(order)
            db_session.flush()
            db_session.add(OrderItem(
                order_id=order.id, product_id=product.id, name=product.name,
                art=product.art, unit_price_cents=montant_cents, qty=1,
            ))

    # Les quatre profils dont les tests connaissent la reponse.
    acheteur("champion@test.fr", commandes=8, recence_jours=2, montant_cents=40000)
    acheteur("recent-unique@test.fr", commandes=1, recence_jours=3, montant_cents=35000)
    acheteur("ancien-unique@test.fr", commandes=1, recence_jours=560, montant_cents=1500)
    acheteur("ancien-gros@test.fr", commandes=6, recence_jours=520, montant_cents=38000)

    # Remplissage : une distribution continue, sans quoi les quintiles se
    # reduiraient a quelques paliers.
    for i in range(20):
        acheteur(
            f"client{i}@test.fr",
            commandes=1 + i % 4,
            recence_jours=20 + i * 22,
            montant_cents=3000 + i * 900,
        )

    db_session.commit()


class TestComparaisonDePeriode:
    def test_base_vide(self, db_session):
        res = analytics.period_overview(db_session, 30)

        assert res["current"]["revenue_cents"] == 0
        # Aucune variation calculable depuis une periode vide.
        assert res["change"]["revenue_cents"] is None

    def test_variation_calculee(self, db_session, product):
        maintenant = datetime.now(timezone.utc)
        # 100 EUR sur la periode precedente, 300 EUR sur la periode courante.
        for jours, montant, numero in [(40, 10000, "A1"), (5, 30000, "A2")]:
            db_session.add(Order(
                number=numero, email="x@test.fr", status="paid",
                subtotal_cents=montant, total_cents=montant,
                created_at=maintenant - timedelta(days=jours),
            ))
        db_session.commit()

        res = analytics.period_overview(db_session, 30)

        assert res["current"]["revenue_cents"] == 30000
        assert res["previous"]["revenue_cents"] == 10000
        assert res["change"]["revenue_cents"] == 2.0  # +200 %

    def test_les_fenetres_ne_se_chevauchent_pas(self, db_session):
        """Une commande ne doit jamais etre comptee dans les deux periodes."""
        maintenant = datetime.now(timezone.utc)
        db_session.add(Order(
            number="B1", email="x@test.fr", status="paid",
            subtotal_cents=5000, total_cents=5000,
            created_at=maintenant - timedelta(days=15),
        ))
        db_session.commit()

        res = analytics.period_overview(db_session, 30)

        assert res["current"]["orders"] + res["previous"]["orders"] == 1


class TestCohortes:
    def test_base_vide(self, db_session):
        res = analytics.cohorts(db_session, 6)

        assert len(res["rows"]) == 6
        assert all(ligne["size"] == 0 for ligne in res["rows"])

    def test_le_futur_d_une_cohorte_reste_indetermine(self, db_session, acheteurs):
        """Une cohorte de ce mois-ci n'a pas de M+3 : la case vaut None, pas 0.

        Afficher zero ferait passer pour un echec une periode qui n'a pas encore
        eu lieu.
        """
        res = analytics.cohorts(db_session, 12)

        recente = res["rows"][-1]
        assert recente["cells"][0] is not None
        assert recente["cells"][1] is None

    def test_taille_et_activite(self, db_session, acheteurs):
        res = analytics.cohorts(db_session, 24)

        # Les trois comptes sont crees le meme mois, il y a 500 jours.
        peuplees = [ligne for ligne in res["rows"] if ligne["size"] > 0]
        assert len(peuplees) == 1
        assert peuplees[0]["size"] == 3

    def test_taux_borne(self, db_session, acheteurs):
        """Un taux de retention ne peut pas depasser 100 %."""
        res = analytics.cohorts(db_session, 24)

        for ligne in res["rows"]:
            for cellule in ligne["cells"]:
                if cellule is not None:
                    assert 0.0 <= cellule["rate"] <= 1.0


class TestSegmentationRFM:
    def test_base_vide(self, db_session):
        res = analytics.rfm_segments(db_session)

        assert res["segments"] == []
        assert res["customers"] == 0

    def test_les_non_acheteurs_sont_comptes_a_part(self, db_session, acheteurs, user_factory):
        user_factory(email="curieux@test.fr")

        res = analytics.rfm_segments(db_session)

        assert res["customers"] == 3
        assert res["non_buyers"] == 1

    def test_un_client_unique_n_est_pas_fidele(self, db_session, population):
        """Regression : le score de montant suffisait a le classer parmi les fideles.

        Un client venu une fois, meme pour un gros montant recent, est nouveau.
        """
        segments = _segments_par_email(db_session)

        assert segments["recent-unique@test.fr"] == "Nouveaux"

    def test_le_client_ancien_sort_des_segments_actifs(self, db_session, population):
        segments = _segments_par_email(db_session)

        assert segments["ancien-unique@test.fr"] in {"Endormis", "A reactiver"}

    def test_le_bon_client_disparu_est_signale_a_risque(self, db_session, population):
        """Le segment ou la relance a le plus de valeur : il a deja prouve qu'il achetait."""
        segments = _segments_par_email(db_session)

        assert segments["ancien-gros@test.fr"] in {"A risque", "A reactiver"}

    def test_le_meilleur_client_est_champion(self, db_session, population):
        segments = _segments_par_email(db_session)

        assert segments["champion@test.fr"] == "Champions"

    def test_les_parts_totalisent_cent_pour_cent(self, db_session, acheteurs):
        res = analytics.rfm_segments(db_session)

        assert sum(s["customers"] for s in res["segments"]) == res["customers"]
        assert round(sum(s["revenue_share"] for s in res["segments"]), 2) == 1.0

    def test_scores_bornes(self, db_session, acheteurs):
        res = analytics.rfm_segments(db_session)

        for exemple in res["examples"]:
            assert all(c in "12345" for c in exemple["scores"])


class TestQuintilesRFM:
    """Notation par quintiles de population.

    Le decoupage a change : il portait sur les valeurs distinctes, il porte
    desormais sur la population. La distinction n'est pas cosmetique - sur le
    jeu de demonstration, elle faisait passer « A risque » de dix-neuf clients
    a cinq mille quatre cents, soit d'un segment decoratif au segment qui pese
    un quart du chiffre d'affaires.

    Ces tests fixent la propriete, pas les valeurs : ils doivent rester vrais
    quelle que soit la distribution.
    """

    def test_les_quintiles_decoupent_la_population(self):
        """Sur cent valeurs distinctes, chaque score prend exactement vingt clients.

        C'est la definition meme d'un quintile, et precisement ce que l'ancienne
        version ne garantissait pas.
        """
        scores = analytics._score_par_rang(list(range(100)), croissant=True)

        effectifs = {score: 0 for score in range(1, 6)}
        for valeur in range(100):
            effectifs[scores[valeur]] += 1

        assert effectifs == {1: 20, 2: 20, 3: 20, 4: 20, 5: 20}

    def test_une_echelle_etiree_ne_trompe_plus_le_decoupage(self):
        """Regression : le defaut qui vidait les segments de relance.

        Quatre-vingt-dix clients tres recents et dix tres anciens, mais des
        anciennetes etalees sur une large echelle. En classant les valeurs
        distinctes, les quatre-vingt-dix recents se partageaient les meilleurs
        scores et personne ne tombait dans les mauvais quintiles. En classant la
        population, les vingt derniers clients obtiennent un score de 1 ou 2,
        quelle que soit l'amplitude de l'echelle.
        """
        valeurs = [jour for jour in range(90)] + [500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400]

        scores = analytics._score_par_rang(valeurs, croissant=True)

        mauvais = [v for v in valeurs if scores[v] <= 2]
        assert len(mauvais) == 40
        # Les dix anciens en font forcement partie : ce sont les pires.
        assert all(scores[v] == 1 for v in (900, 1000, 1100, 1200, 1300, 1400))

    def test_les_ex_aequo_partagent_leur_score(self):
        """Deux clients de meme valeur doivent etre notes pareil.

        Sans cette garantie, le score dependrait de l'ordre dans lequel la base
        rend les lignes - il changerait donc d'une lecture a l'autre.
        """
        valeurs = [10] * 30 + [20] * 30 + [30] * 40

        scores = analytics._score_par_rang(valeurs, croissant=False)

        # Trois valeurs distinctes, trois scores, et chacun ne depend que de la
        # valeur.
        assert len({scores[10], scores[20], scores[30]}) == 3
        assert scores[30] > scores[20] > scores[10]

    def test_un_gros_groupe_est_juge_sur_son_milieu(self):
        """Un paquet d'ex aequo plus large qu'un quintile prend la note de son centre.

        La majorite des clients n'ayant commande qu'une fois, les juger sur
        l'extremite basse de leur groupe les deprecierait tous. La convention
        des rangs moyens vise le milieu : un groupe occupant les 70 % du bas est
        centre sur 65 %, donc note 2 - et non 1, qui serait la note de son pire
        element.
        """
        valeurs = [5] * 30 + [1] * 70

        scores = analytics._score_par_rang(valeurs, croissant=False)

        assert scores[5] == 5   # groupe du haut, centre sur 15 %
        assert scores[1] == 2   # groupe du bas, centre sur 65 %

    def test_un_groupe_a_cheval_sur_une_borne_bascule_vers_le_bas(self):
        """Cas limite assume : le centre d'un groupe peut tomber sur une frontiere.

        Un groupe occupant les 40 % du haut est centre exactement sur le
        vingtieme centile, borne entre le premier et le deuxieme quintile. Il
        bascule alors dans le second, donc 4 et non 5.

        Documente ici parce que c'est surprenant a la lecture d'un resultat, et
        parce que l'entrepot doit se comporter pareil : `floor` cote SQL et
        `int` cote Python arrondissent tous deux vers le bas, ce qui est la
        condition pour que les deux chemins ne divergent jamais sur ce cas.
        """
        scores = analytics._score_par_rang([5] * 40 + [1] * 60, croissant=False)

        assert scores[5] == 4

    def test_valeurs_vides(self):
        assert analytics._score_par_rang([], croissant=True) == {}

    def test_un_client_seul_est_note_a_la_mediane(self):
        """Un client unique n'est ni le meilleur ni le pire : il est la mediane.

        Le score le plus eleve recompense une position relative, et il n'y a
        aucune position relative a occuper quand on est seul. Le noter 5
        laisserait croire a un champion la ou il n'y a qu'un echantillon d'une
        personne ; 3 dit ce qu'il en est - le milieu d'une distribution qui se
        reduit a lui.

        C'est la meme limite que celle rappelee par `rfm_segments` : sur une
        poignee d'acheteurs, les quintiles ne separent plus rien.
        """
        assert analytics._score_par_rang([42], croissant=True) == {42: 3}


class TestRecenceEnJoursDeCalendrier:
    def test_une_commande_d_hier_soir_compte_pour_un_jour(self, db_session, user_factory):
        """Regression : la recence dependait de l'heure autant que de la date.

        `(maintenant - derniere).days` compte des tranches de vingt-quatre
        heures : une commande passee hier a 23 h y valait zero jour. L'entrepot,
        lui, soustrait deux dates. Les deux chemins classaient donc une poignee
        de clients differemment, et deux segmentations contradictoires selon
        l'onglet ouvert ne sont credibles ni l'une ni l'autre.
        """
        user, _ = user_factory(email="hier@test.fr")
        hier_soir = datetime.now(timezone.utc).replace(hour=23, minute=0) - timedelta(days=1)
        commande = Order(
            number="RFM-HIER", user_id=user.id, email=user.email, status="paid",
            subtotal_cents=1000, total_cents=1000, created_at=hier_soir,
        )
        db_session.add(commande)
        db_session.commit()

        res = analytics.rfm_segments(db_session)
        recences = {e["email"]: e["recency_days"] for e in res["examples"]}

        assert recences["hier@test.fr"] == 1


class TestAffinites:
    def test_base_vide(self, db_session):
        res = analytics.affinities(db_session)

        assert res["pairs"] == []
        assert res["orders"] == 0

    def test_paire_systematique(self, db_session, product, expensive_product):
        """Deux articles toujours achetes ensemble : lift maximal.

        Quand A et B apparaissent dans exactement les memes commandes, la
        confiance vaut 1 et le lift vaut l'inverse de la frequence de B. Avec
        dix commandes sur dix, le lift vaut donc 1.
        """
        for i in range(10):
            order = Order(
                number=f"C{i}", email="x@test.fr", status="paid",
                subtotal_cents=11000, total_cents=11000,
            )
            db_session.add(order)
            db_session.flush()
            for p in (product, expensive_product):
                db_session.add(OrderItem(
                    order_id=order.id, product_id=p.id, name=p.name,
                    art=p.art, unit_price_cents=p.price_cents, qty=1,
                ))
        db_session.commit()

        res = analytics.affinities(db_session)

        assert len(res["pairs"]) == 1
        regle = res["pairs"][0]
        assert regle["orders_together"] == 10
        assert regle["support"] == 1.0
        assert regle["confidence_ab"] == 1.0
        assert regle["lift"] == 1.0

    def test_le_seuil_de_support_ecarte_le_bruit(self, db_session, product, expensive_product):
        """Une seule commande commune ne constitue pas une regle."""
        order = Order(
            number="D1", email="x@test.fr", status="paid",
            subtotal_cents=11000, total_cents=11000,
        )
        db_session.add(order)
        db_session.flush()
        for p in (product, expensive_product):
            db_session.add(OrderItem(
                order_id=order.id, product_id=p.id, name=p.name,
                art=p.art, unit_price_cents=p.price_cents, qty=1,
            ))
        db_session.commit()

        res = analytics.affinities(db_session)

        assert res["pairs"] == []

    def test_chaque_paire_n_apparait_qu_une_fois(self, db_session, product, expensive_product):
        for i in range(10):
            order = Order(
                number=f"E{i}", email="x@test.fr", status="paid",
                subtotal_cents=11000, total_cents=11000,
            )
            db_session.add(order)
            db_session.flush()
            for p in (product, expensive_product):
                db_session.add(OrderItem(
                    order_id=order.id, product_id=p.id, name=p.name,
                    art=p.art, unit_price_cents=p.price_cents, qty=1,
                ))
        db_session.commit()

        res = analytics.affinities(db_session)

        couples = {(r["a_id"], r["b_id"]) for r in res["pairs"]}
        inverses = {(r["b_id"], r["a_id"]) for r in res["pairs"]}
        assert not (couples & inverses)


class TestRoutes:
    @pytest.fixture
    def admin(self, auth_header):
        headers, _ = auth_header(email="patron@hanabi.fr", is_admin=True)
        return headers

    @pytest.mark.parametrize(
        "route",
        ["/admin/analytics", "/admin/analytics/cohorts",
         "/admin/analytics/segments", "/admin/analytics/affinities"],
    )
    def test_reservees_aux_administrateurs(self, client, auth_header, route):
        headers, _ = auth_header(email="client@test.fr", is_admin=False)

        assert client.get(route).status_code == 401
        assert client.get(route, headers=headers).status_code == 403

    @pytest.mark.parametrize(
        "route",
        ["/admin/analytics", "/admin/analytics/cohorts",
         "/admin/analytics/segments", "/admin/analytics/affinities"],
    )
    def test_repondent_sur_une_base_vide(self, client, admin, route):
        assert client.get(route, headers=admin).status_code == 200

    def test_parametres_bornes(self, client, admin):
        assert client.get("/admin/analytics?days=1", headers=admin).status_code == 422
        assert client.get("/admin/analytics?days=9999", headers=admin).status_code == 422
        assert client.get("/admin/analytics/cohorts?months=99", headers=admin).status_code == 422

    def test_vue_d_ensemble_complete(self, client, admin):
        corps = client.get("/admin/analytics?days=30", headers=admin).json()

        assert set(corps) >= {
            "period", "kpis", "series", "products",
            "categories", "promos", "statuses", "top_customers",
        }
        assert set(corps["period"]) >= {"current", "previous", "change"}
