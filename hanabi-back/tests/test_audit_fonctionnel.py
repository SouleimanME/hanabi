"""Défauts trouvés à l'audit de septembre 2026, et le test qui les tient fermés.

Chaque classe décrit ce qui ne marchait pas, du point de vue de la personne qui
l'aurait vécu.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from antibot_helper import solve_antibot
from test_orders import checkout_payload

from app import abonnement, models, payments, rgpd
from app.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, ensure_public_admin


@pytest.fixture
def demo_admin(db_session, client):
    ensure_public_admin(db_session)
    res = client.post(
        "/auth/login",
        json={"email": DEMO_ADMIN_EMAIL, "password": DEMO_ADMIN_PASSWORD, "antibot": solve_antibot("login")},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def vrai_admin(auth_header):
    entete, _ = auth_header(email="patron@hanabi.fr", is_admin=True)
    return entete


def _courriels(db_session, destinataire=None):
    db_session.expire_all()
    requete = select(models.OutboxEmail)
    if destinataire:
        requete = requete.where(models.OutboxEmail.destinataire == destinataire)
    return db_session.scalars(requete).all()


def _commande_de(db_session, compte, produit, numero="ATL900001", statut="paid"):
    commande = models.Order(
        number=numero, user_id=compte.id if compte else None,
        email=compte.email if compte else "invite@exemple.fr", status=statut,
        subtotal_cents=produit.price_cents, discount_cents=0, shipping_cents=0,
        total_cents=produit.price_cents, ship_name="Marie Durand",
        ship_addr="3 rue des Lilas", ship_cp="69003", ship_city="Lyon",
    )
    db_session.add(commande)
    db_session.flush()
    db_session.add(models.OrderItem(
        order_id=commande.id, product_id=produit.id, name=produit.name,
        art=produit.art, category=produit.category, unit_price_cents=produit.price_cents, qty=2,
    ))
    db_session.commit()
    return commande


class TestComptePublicDuBackOffice:
    """Ses identifiants sont affichés à la connexion ; il lisait pourtant des adresses en clair."""

    @pytest.fixture
    def cliente(self, db_session, user_factory, product):
        compte, _ = user_factory(email="marie.durand@exemple.fr", name="Marie Durand")
        compte.city = "Lyon"
        db_session.commit()
        _commande_de(db_session, compte, product)
        db_session.add(models.StockAlert(product_id=product.id, email="alerte@exemple.fr"))
        db_session.commit()
        return compte

    @pytest.mark.parametrize("route", [
        "/admin/stats", "/admin/orders", "/admin/alerts", "/admin/analytics",
        "/admin/analytics/segments", "/admin/analytics/audience",
    ])
    def test_aucune_adresse_en_clair(self, client, demo_admin, cliente, route):
        corps = client.get(route, headers=demo_admin).text
        assert "marie.durand@exemple.fr" not in corps
        assert "alerte@exemple.fr" not in corps
        assert "3 rue des Lilas" not in corps

    def test_le_vrai_administrateur_lit_tout(self, client, vrai_admin, cliente):
        commandes = client.get("/admin/orders", headers=vrai_admin).json()
        premiere = commandes["items"][0]
        assert premiere["email"] == "marie.durand@exemple.fr"
        assert premiere["ship_addr"] == "3 rue des Lilas"
        alertes = client.get("/admin/alerts", headers=vrai_admin).json()
        assert alertes[0]["email"] == "alerte@exemple.fr"

    def test_la_console_ne_propose_que_les_agregats(self, client, demo_admin, vrai_admin):
        aide_demo = client.get("/admin/warehouse/sql/aide", headers=demo_admin).json()
        aide_admin = client.get("/admin/warehouse/sql/aide", headers=vrai_admin).json()

        assert aide_demo["schemas"] == ["controles", "externe", "gold"]
        assert "silver" in aide_admin["schemas"]
        assert all("silver." not in e["sql"] for e in aide_demo["exemples"])
        assert any("silver." in e["sql"] for e in aide_admin["exemples"])


class TestAdresseSaisieAvecUneCapitale:
    """Un téléphone met une capitale en tête ; le compte ne se retrouvait plus ailleurs."""

    def test_inscription_puis_connexion_en_minuscules(self, client, db_session):
        inscription = client.post("/auth/register", json={
            "name": "Marie Durand", "email": "Marie.Durand@Exemple.fr",
            "password": "Secret-pour-2026", "antibot": solve_antibot("register"),
            "civility": "F", "birthdate": "1990-04-12",
        })
        assert inscription.status_code == 201, inscription.text
        assert inscription.json()["user"]["email"] == "marie.durand@exemple.fr"

        connexion = client.post("/auth/login", json={
            "email": "marie.durand@exemple.fr", "password": "Secret-pour-2026",
            "antibot": solve_antibot("login"),
        })
        assert connexion.status_code == 200

    def test_un_ancien_compte_a_capitale_se_connecte_et_recupere_son_mot_de_passe(
        self, client, db_session, user_factory
    ):
        user_factory(email="Paul.Martin@Exemple.fr", password="MotDePasse1!")

        connexion = client.post("/auth/login", json={
            "email": "paul.martin@exemple.fr", "password": "MotDePasse1!",
            "antibot": solve_antibot("login"),
        })
        assert connexion.status_code == 200

        client.post("/auth/forgot-password", json={"email": "paul.martin@exemple.fr"})
        assert _courriels(db_session, "Paul.Martin@Exemple.fr")

    def test_une_date_de_naissance_malformee_est_refusee(self, client):
        res = client.post("/auth/register", json={
            "name": "Marie", "email": "m@exemple.fr", "password": "Secret-pour-2026",
            "antibot": solve_antibot("register"), "birthdate": "12/04/1990",
        })
        assert res.status_code == 422


class TestNumeroDeCommande:
    """Le jeu de démonstration occupe 7 % des numéros : une commande sur quinze échouait en 500."""

    def test_un_numero_deja_pris_est_retire(self, client, db_session, product, monkeypatch):
        _commande_de(db_session, None, product, numero="ATL111111")
        tirages = iter(["ATL111111", "ATL111111", "ATL222222"])
        monkeypatch.setattr(payments, "nouvelle_reference_commande", lambda: next(tirages))

        res = client.post("/orders/checkout", json=checkout_payload(product.id))

        assert res.status_code == 201, res.text
        assert res.json()["number"] == "ATL222222"


class TestAdresseDeLivraison:
    """Le paiement demandait une adresse et la jetait : rien à expédier, rien à exporter."""

    def test_l_adresse_est_gardee_et_rappelee_dans_le_courriel(self, client, db_session, product):
        res = client.post("/orders/checkout", json=checkout_payload(product.id, email="ada@exemple.fr"))
        assert res.status_code == 201, res.text
        corps = res.json()
        assert corps["ship_name"] == "Ada Lovelace"
        assert corps["ship_city"] == "Paris"

        courriel = _courriels(db_session, "ada@exemple.fr")[0]
        assert "12 rue des Tests" in courriel.texte
        assert "75001 Paris" in courriel.html

    def test_une_adresse_vide_est_refusee(self, client, product):
        charge = checkout_payload(product.id)
        charge["shipping"]["adresse"] = "   "
        assert client.post("/orders/checkout", json=charge).status_code == 422

    def test_l_effacement_retire_l_adresse(self, db_session, user_factory, product):
        compte, _ = user_factory(email="partante@exemple.fr")
        commande = _commande_de(db_session, compte, product)

        rgpd.anonymiser(db_session, compte)
        db_session.commit()
        db_session.refresh(commande)

        assert commande.ship_addr is None and commande.ship_name is None

    def test_l_export_contient_l_adresse_et_les_alertes(self, db_session, user_factory, product):
        compte, _ = user_factory(email="curieuse@exemple.fr")
        _commande_de(db_session, compte, product)
        db_session.add(models.StockAlert(product_id=product.id, email="curieuse@exemple.fr"))
        db_session.commit()

        export = rgpd.exporter(db_session, compte)

        assert export["commandes"][0]["livraison"]["ville"] == "Lyon"
        assert export["alertes_de_retour_en_stock"][0]["produit_id"] == product.id


class TestRetourEnStock:
    """La fiche promettait un e-mail au retour en stock ; aucun code ne l'envoyait."""

    @pytest.fixture
    def epuise(self, db_session, product):
        product.stock = 0
        db_session.commit()
        return product

    def _alerte(self, client, produit, email, lang="fr"):
        return client.post(
            f"/products/{produit.id}/notify",
            json={"email": email, "lang": lang, "antibot": solve_antibot("notify")},
        )

    def test_le_reassort_previent_dans_la_langue_de_la_page(
        self, client, db_session, vrai_admin, epuise
    ):
        assert self._alerte(client, epuise, "Yuki@Exemple.jp", lang="en").status_code == 201

        res = client.patch(f"/admin/products/{epuise.id}", headers=vrai_admin, json={"stock": 4})

        assert res.json()["alertes_envoyees"] == 1
        courriel = _courriels(db_session, "yuki@exemple.jp")[0]
        assert courriel.sujet.endswith("is back")
        assert f"/produit/{epuise.id}" in courriel.texte

    def test_un_seul_courriel_par_demande(self, client, db_session, vrai_admin, epuise):
        self._alerte(client, epuise, "une@exemple.fr")
        client.patch(f"/admin/products/{epuise.id}", headers=vrai_admin, json={"stock": 4})
        client.patch(f"/admin/products/{epuise.id}", headers=vrai_admin, json={"stock": 9})

        assert len(_courriels(db_session, "une@exemple.fr")) == 1

    def test_une_annulation_remet_en_stock_et_previent(
        self, client, db_session, vrai_admin, epuise, user_factory
    ):
        compte, _ = user_factory(email="acheteuse@exemple.fr")
        commande = _commande_de(db_session, compte, epuise)
        self._alerte(client, epuise, "attente@exemple.fr")

        res = client.patch(
            f"/admin/orders/{commande.number}/status?status=cancelled", headers=vrai_admin
        )

        assert res.status_code == 200, res.text
        assert res.json()["remis_en_stock"] == 2
        db_session.refresh(epuise)
        assert epuise.stock == 2
        assert _courriels(db_session, "attente@exemple.fr")


class TestDesinscription:
    """Le courriel de bienvenue renvoyait vers /desinscription, qui n'existait pas."""

    def _inscrire(self, client, email="lecteur@exemple.fr", lang="fr"):
        return client.post(
            "/newsletter/subscribe",
            json={"email": email, "lang": lang, "antibot": solve_antibot("subscribe")},
        )

    def _lien(self, db_session, email="lecteur@exemple.fr"):
        courriel = _courriels(db_session, email)[0]
        lien = next(mot for mot in courriel.texte.split() if "/desinscription?" in mot)
        return lien, parse_qs(urlparse(lien).query)

    def test_le_lien_du_courriel_desinscrit(self, client, db_session):
        self._inscrire(client)
        _, requete = self._lien(db_session)

        res = client.post(
            "/newsletter/unsubscribe",
            json={"id": int(requete["i"][0]), "signature": requete["s"][0]},
        )

        assert res.json() == {"ok": True, "deja": False, "email": "l***r@exemple.fr"}
        db_session.expire_all()
        inscrit = db_session.scalar(select(models.Subscriber))
        assert inscrit.unsubscribed is True

    def test_le_lien_ne_contient_pas_l_adresse(self, client, db_session):
        self._inscrire(client)
        lien, _ = self._lien(db_session)
        assert "lecteur" not in lien and "%40" not in lien

    def test_une_signature_fausse_est_refusee(self, client, db_session):
        self._inscrire(client)
        _, requete = self._lien(db_session)
        res = client.post(
            "/newsletter/unsubscribe",
            json={"id": int(requete["i"][0]), "signature": "0" * 64},
        )
        assert res.status_code == 400

    def test_le_courriel_suit_la_langue_de_la_page(self, client, db_session):
        self._inscrire(client, email="reader@exemple.com", lang="en")
        courriel = _courriels(db_session, "reader@exemple.com")[0]
        assert "Unsubscribe" in courriel.texte
        assert 'lang="en"' in courriel.html

    def test_une_inscription_disparue_repond_sans_erreur(self, client):
        res = client.post(
            "/newsletter/unsubscribe",
            json={"id": 999, "signature": abonnement.signature(999)},
        )
        assert res.json() == {"ok": True, "deja": True, "email": None}


class TestSuppressionDeProduit:
    """Un produit vu mais jamais vendu : la suppression cassait une clé étrangère (500 sur PostgreSQL)."""

    def test_un_produit_consulte_est_retire_de_la_vente(self, client, db_session, vrai_admin, product):
        db_session.add(models.ProductView(product_id=product.id))
        db_session.commit()

        res = client.delete(f"/admin/products/{product.id}", headers=vrai_admin)

        assert res.json() == {"action": "desactive"}
        db_session.refresh(product)
        assert product.active is False

    def test_un_produit_vierge_est_supprime(self, client, db_session, vrai_admin, product):
        res = client.delete(f"/admin/products/{product.id}", headers=vrai_admin)
        assert res.json() == {"action": "supprime"}


class TestCodesPromo:
    def test_un_pourcentage_sans_taux_est_refuse(self, client, vrai_admin):
        res = client.post("/admin/promos", headers=vrai_admin, json={"code": "TROU", "kind": "percent"})
        assert res.status_code == 422

    def test_renommer_vers_un_code_existant_est_refuse(self, client, vrai_admin, promos):
        cible = promos["fixed"]
        res = client.patch(f"/admin/promos/{cible.id}", headers=vrai_admin, json={
            "code": "moins10", "kind": "fixed", "amount_cents": 500,
        })
        assert res.status_code == 409

    def test_l_echeance_peut_etre_retiree(self, client, db_session, vrai_admin, promos):
        cible = promos["percent"]
        cible.expires_at = datetime.now(timezone.utc) + timedelta(days=3)
        db_session.commit()

        client.patch(f"/admin/promos/{cible.id}", headers=vrai_admin, json={
            "code": "MOINS10", "kind": "percent", "percent": 10, "expires_at": None,
        })

        db_session.refresh(cible)
        assert cible.expires_at is None


class TestStatutsDeCommande:
    """Une commande livrée pouvait redevenir payée par un simple appel."""

    def test_un_retour_en_arriere_est_refuse(self, client, db_session, vrai_admin, product):
        commande = _commande_de(db_session, None, product, statut="delivered")
        res = client.patch(f"/admin/orders/{commande.number}/status?status=paid", headers=vrai_admin)
        assert res.status_code == 409
        assert "livrée" in res.json()["detail"]

    def test_la_liste_annonce_les_suivants(self, client, db_session, vrai_admin, product):
        _commande_de(db_session, None, product, statut="paid")
        item = client.get("/admin/orders", headers=vrai_admin).json()["items"][0]
        assert item["next"] == ["cancelled", "shipped"]


class TestRechercheDesCommandes:
    """La recherche ne portait que sur les cent commandes chargées."""

    def test_la_recherche_porte_sur_toute_la_base(self, client, db_session, vrai_admin, product):
        _commande_de(db_session, None, product, numero="ATL424242")
        for i in range(120):
            _commande_de(db_session, None, product, numero=f"ATL5{i:05d}")

        res = client.get("/admin/orders?q=atl424242&limit=50", headers=vrai_admin).json()

        assert res["total"] == 1
        assert res["items"][0]["number"] == "ATL424242"


class TestRechercheDuCatalogue:
    """En anglais, « mask » ne trouvait rien : la recherche lisait le nom français."""

    @pytest.fixture
    def masque(self, db_session):
        p = models.Product(
            code="HNB-061", name="Masque Kitsune", category="Décoration",
            blurb="Résine peinte main", price_cents=3900, stock=5, art="kitsune,#E0452A,#0A0605",
        )
        eventail = models.Product(
            code="HNB-037", name="Éventail Sensu", category="Décoration",
            blurb="Bambou et washi", price_cents=2800, stock=5, art="fan,#0A0605,#D8452B",
        )
        db_session.add_all([p, eventail])
        db_session.commit()
        return p

    def test_le_nom_traduit_est_cherche(self, client, masque):
        noms = [p["name"] for p in client.get("/products?q=mask&lang=en").json()]
        assert noms == ["Kitsune Mask"]

    def test_les_accents_ne_comptent_pas(self, client, masque):
        noms = [p["name"] for p in client.get("/products?q=eventail").json()]
        assert noms == ["Éventail Sensu"]
