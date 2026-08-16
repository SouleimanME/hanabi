"""Gestion de son propre compte : profil, identifiants, moyens de paiement.

Deux familles de garanties sont verifiees ici, et la seconde compte plus que la
premiere :

  1. les modifications font ce qu'elles annoncent ;
  2. on ne peut PAS toucher au compte d'un autre, ni faire changer un mot de
     passe ou une adresse sans prouver qu'on est bien la maintenant.
"""
import pytest

from app import models

from antibot_helper import solve_antibot

from test_orders import checkout_payload


MOT_DE_PASSE = "Correct-Cheval-Pile-9"
CARTE = {
    "reseau": "visa",
    "quatre_derniers": "4242",
    "exp_mois": 12,
    "exp_annee": 2030,
}


@pytest.fixture
def compte(client, auth_header):
    """Un compte connecte, avec son mot de passe connu du test."""
    headers, user = auth_header(email="ada@test.fr", password=MOT_DE_PASSE)
    return headers, user


class TestProfil:
    def test_modifie_les_champs_fournis(self, client, db_session, compte):
        headers, user = compte

        res = client.patch("/compte/profil", json={"phone": "0612345678"}, headers=headers)

        assert res.status_code == 200
        assert res.json()["phone"] == "0612345678"
        db_session.refresh(user)
        assert user.phone == "0612345678"

    def test_ne_touche_pas_aux_champs_absents(self, client, db_session, compte):
        """LE piege de ces formulaires.

        Un ecran qui n'envoie que le telephone ne doit pas effacer l'adresse, la
        ville et le code postal - tous absents du corps, donc tous vus comme
        `None` si l'on ne distingue pas « absent » de « vide ».
        """
        headers, user = compte
        user.city = "Kyoto"
        user.addr = "3 rue des Erables"
        db_session.commit()

        client.patch("/compte/profil", json={"phone": "0612345678"}, headers=headers)

        db_session.refresh(user)
        assert user.city == "Kyoto"
        assert user.addr == "3 rue des Erables"

    def test_une_chaine_vide_efface_un_champ_facultatif(self, client, db_session, compte):
        headers, user = compte
        user.phone = "0612345678"
        db_session.commit()

        client.patch("/compte/profil", json={"phone": ""}, headers=headers)

        db_session.refresh(user)
        assert user.phone is None

    def test_une_chaine_vide_n_efface_pas_le_nom(self, client, db_session, compte):
        """Un compte sans nom n'a pas de sens : c'est une faute de frappe, pas
        une intention."""
        headers, user = compte
        avant = user.name

        client.patch("/compte/profil", json={"name": "   "}, headers=headers)

        db_session.refresh(user)
        assert user.name == avant

    def test_les_espaces_sont_retires(self, client, db_session, compte):
        headers, user = compte

        client.patch("/compte/profil", json={"city": "  Paris  "}, headers=headers)

        db_session.refresh(user)
        assert user.city == "Paris"

    def test_un_corps_vide_ne_change_rien(self, client, compte):
        headers, _ = compte
        assert client.patch("/compte/profil", json={}, headers=headers).status_code == 200

    def test_une_civilite_inconnue_est_refusee(self, client, compte):
        headers, _ = compte
        res = client.patch("/compte/profil", json={"civility": "X"}, headers=headers)
        assert res.status_code == 422

    def test_ferme_sans_authentification(self, client):
        assert client.patch("/compte/profil", json={"phone": "06"}).status_code in (401, 403)

    def test_l_email_ne_se_change_pas_par_cette_route(self, client, db_session, compte):
        """Il engage l'ACCES au compte, pas son contenu : route dediee, mot de
        passe exige."""
        headers, user = compte
        avant = user.email

        client.patch("/compte/profil", json={"email": "autre@test.fr"}, headers=headers)

        db_session.refresh(user)
        assert user.email == avant


class TestChangementMotDePasse:
    def test_change_avec_l_ancien(self, client, compte):
        headers, _ = compte
        res = client.post(
            "/compte/mot-de-passe",
            json={"ancien": MOT_DE_PASSE, "nouveau": "Nouveau-Passe-Robuste-42"},
            headers=headers,
        )

        assert res.status_code == 204
        connexion = client.post(
            "/auth/login",
            json={
                "email": "ada@test.fr",
                "password": "Nouveau-Passe-Robuste-42",
                "antibot": solve_antibot("login"),
            },
        )
        assert connexion.status_code == 200

    def test_refuse_sans_l_ancien(self, client, compte):
        """Une session prouve qu'on etait la il y a douze heures, pas qu'on est
        la maintenant. Un poste laisse ouvert suffirait sinon a verrouiller le
        proprietaire hors de son compte.
        """
        headers, _ = compte
        res = client.post(
            "/compte/mot-de-passe",
            json={"ancien": "pas-le-bon", "nouveau": "Nouveau-Passe-Robuste-42"},
            headers=headers,
        )

        assert res.status_code == 403

    def test_refuse_un_mot_de_passe_faible(self, client, compte):
        """Un parcours de changement n'est pas une occasion d'assouplir la
        politique."""
        headers, _ = compte
        res = client.post(
            "/compte/mot-de-passe",
            json={"ancien": MOT_DE_PASSE, "nouveau": "abc"},
            headers=headers,
        )
        assert res.status_code == 422

    def test_refuse_le_meme_mot_de_passe(self, client, compte):
        headers, _ = compte
        res = client.post(
            "/compte/mot-de-passe",
            json={"ancien": MOT_DE_PASSE, "nouveau": MOT_DE_PASSE},
            headers=headers,
        )
        assert res.status_code == 422

    def test_revoque_les_liens_de_reinitialisation_en_cours(self, client, db_session, compte):
        """Quelqu'un qui change son mot de passe le fait souvent parce qu'il
        doute : laisser vivre un lien demande une heure plus tot annulerait le
        geste."""
        headers, _ = compte
        client.post("/auth/forgot-password", json={"email": "ada@test.fr"})
        assert db_session.query(models.Token).filter_by(utilise_le=None).count() == 1

        client.post(
            "/compte/mot-de-passe",
            json={"ancien": MOT_DE_PASSE, "nouveau": "Nouveau-Passe-Robuste-42"},
            headers=headers,
        )

        assert db_session.query(models.Token).filter_by(utilise_le=None).count() == 0


class TestChangementEmail:
    def test_change_avec_le_mot_de_passe(self, client, db_session, compte):
        headers, user = compte
        res = client.post(
            "/compte/email",
            json={"email": "ada.nouvelle@test.fr", "password": MOT_DE_PASSE},
            headers=headers,
        )

        assert res.status_code == 200
        db_session.refresh(user)
        assert user.email == "ada.nouvelle@test.fr"

    def test_la_nouvelle_adresse_repart_non_confirmee(self, client, db_session, compte):
        """Sinon il suffirait de confirmer une adresse quelconque puis d'en
        declarer une autre pour se retrouver « confirme » sur une boite dont on
        n'a jamais prouve l'acces."""
        headers, user = compte
        user.email_verified = True
        db_session.commit()

        client.post(
            "/compte/email",
            json={"email": "ada.nouvelle@test.fr", "password": MOT_DE_PASSE},
            headers=headers,
        )

        db_session.refresh(user)
        assert user.email_verified is False

    def test_un_lien_part_sur_la_nouvelle_adresse(self, client, db_session, compte):
        headers, _ = compte
        client.post(
            "/compte/email",
            json={"email": "ada.nouvelle@test.fr", "password": MOT_DE_PASSE},
            headers=headers,
        )

        message = (
            db_session.query(models.OutboxEmail)
            .order_by(models.OutboxEmail.id.desc())
            .first()
        )
        assert message.destinataire == "ada.nouvelle@test.fr"

    def test_refuse_sans_le_mot_de_passe(self, client, db_session, compte):
        headers, user = compte
        res = client.post(
            "/compte/email",
            json={"email": "ada.nouvelle@test.fr", "password": "pas-le-bon"},
            headers=headers,
        )

        assert res.status_code == 403
        db_session.refresh(user)
        assert user.email == "ada@test.fr"

    def test_refuse_une_adresse_deja_prise(self, client, auth_header, compte):
        auth_header(email="occupee@test.fr")
        headers, _ = compte

        res = client.post(
            "/compte/email",
            json={"email": "occupee@test.fr", "password": MOT_DE_PASSE},
            headers=headers,
        )
        assert res.status_code == 409

    def test_refuse_sa_propre_adresse(self, client, compte):
        headers, _ = compte
        res = client.post(
            "/compte/email", json={"email": "ada@test.fr", "password": MOT_DE_PASSE}, headers=headers
        )
        assert res.status_code == 422


class TestMoyensDePaiement:
    def test_ajoute_une_carte(self, client, compte):
        headers, _ = compte
        res = client.post("/compte/paiements", json=CARTE, headers=headers)

        assert res.status_code == 201
        body = res.json()
        assert body["reseau"] == "visa"
        assert body["quatre_derniers"] == "4242"

    def test_le_jeton_n_est_jamais_renvoye(self, client, compte):
        """Il sert a debiter : l'interface n'a aucune raison de le connaitre."""
        headers, _ = compte
        corps = client.post("/compte/paiements", json=CARTE, headers=headers).text

        assert "jeton" not in corps
        assert "pm_" not in corps

    def test_aucun_numero_complet_n_est_accepte(self, client, db_session, compte):
        """Le schema n'a pas de champ pour cela, et c'est le but.

        Ce que la table ne contient pas ne peut pas etre vole : c'est ce qui
        maintient l'application hors du perimetre PCI-DSS.
        """
        headers, _ = compte
        client.post(
            "/compte/paiements",
            json={**CARTE, "numero": "4242424242424242", "cvc": "123"},
            headers=headers,
        )

        colonnes = {c.name for c in models.PaymentMethod.__table__.columns}
        assert "numero" not in colonnes
        assert "cvc" not in colonnes
        moyen = db_session.query(models.PaymentMethod).one()
        assert not hasattr(moyen, "numero")

    def test_la_premiere_carte_devient_le_defaut(self, client, compte):
        """Personne n'enregistre une carte pour ne pas s'en servir."""
        headers, _ = compte
        assert client.post("/compte/paiements", json=CARTE, headers=headers).json()["defaut"]

    def test_une_seule_carte_par_defaut(self, client, compte):
        headers, _ = compte
        client.post("/compte/paiements", json=CARTE, headers=headers)
        client.post(
            "/compte/paiements",
            json={**CARTE, "quatre_derniers": "5555", "defaut": True},
            headers=headers,
        )

        liste = client.get("/compte/paiements", headers=headers).json()
        assert [m["defaut"] for m in liste].count(True) == 1
        assert liste[0]["quatre_derniers"] == "5555"

    def test_change_la_carte_par_defaut(self, client, compte):
        headers, _ = compte
        premiere = client.post("/compte/paiements", json=CARTE, headers=headers).json()
        client.post(
            "/compte/paiements", json={**CARTE, "quatre_derniers": "5555"}, headers=headers
        )

        client.post(f"/compte/paiements/{premiere['id']}/defaut", headers=headers)

        liste = client.get("/compte/paiements", headers=headers).json()
        assert [m["defaut"] for m in liste].count(True) == 1
        assert liste[0]["id"] == premiere["id"]

    def test_supprime_une_carte(self, client, compte):
        headers, _ = compte
        moyen = client.post("/compte/paiements", json=CARTE, headers=headers).json()

        assert client.delete(f"/compte/paiements/{moyen['id']}", headers=headers).status_code == 204
        assert client.get("/compte/paiements", headers=headers).json() == []

    def test_supprimer_le_defaut_en_designe_un_autre(self, client, compte):
        """Sinon le paiement suivant proposerait une liste sans selection, ce
        qui se lit comme un oubli de l'application."""
        headers, _ = compte
        premiere = client.post("/compte/paiements", json=CARTE, headers=headers).json()
        client.post(
            "/compte/paiements", json={**CARTE, "quatre_derniers": "5555"}, headers=headers
        )

        client.delete(f"/compte/paiements/{premiere['id']}", headers=headers)

        restantes = client.get("/compte/paiements", headers=headers).json()
        assert len(restantes) == 1
        assert restantes[0]["defaut"] is True

    def test_plafonne_le_nombre_de_cartes(self, client, compte):
        headers, _ = compte
        from app.routers.compte import MAX_MOYENS_PAIEMENT

        for i in range(MAX_MOYENS_PAIEMENT):
            res = client.post(
                "/compte/paiements",
                json={**CARTE, "quatre_derniers": f"{1000 + i}"},
                headers=headers,
            )
            assert res.status_code == 201

        assert client.post("/compte/paiements", json=CARTE, headers=headers).status_code == 422

    @pytest.mark.parametrize(
        "invalide",
        [
            {"reseau": "bitcoin"},
            {"quatre_derniers": "42"},
            {"quatre_derniers": "abcd"},
            {"exp_mois": 13},
            {"exp_mois": 0},
            {"exp_annee": 1999},
        ],
    )
    def test_refuse_une_carte_malformee(self, client, compte, invalide):
        headers, _ = compte
        res = client.post("/compte/paiements", json={**CARTE, **invalide}, headers=headers)
        assert res.status_code == 422


class TestCloisonnement:
    """La garantie qui compte le plus : on ne touche qu'a son propre compte."""

    def test_on_ne_voit_pas_les_cartes_d_un_autre(self, client, auth_header, compte):
        headers_ada, _ = compte
        client.post("/compte/paiements", json=CARTE, headers=headers_ada)

        headers_bob, _ = auth_header(email="bob@test.fr")

        assert client.get("/compte/paiements", headers=headers_bob).json() == []

    def test_on_ne_supprime_pas_la_carte_d_un_autre(self, client, auth_header, compte):
        headers_ada, _ = compte
        moyen = client.post("/compte/paiements", json=CARTE, headers=headers_ada).json()

        headers_bob, _ = auth_header(email="bob@test.fr")
        res = client.delete(f"/compte/paiements/{moyen['id']}", headers=headers_bob)

        # 404 et non 403 : un 403 confirmerait que la ligne existe.
        assert res.status_code == 404
        assert len(client.get("/compte/paiements", headers=headers_ada).json()) == 1

    def test_on_ne_promeut_pas_la_carte_d_un_autre(self, client, auth_header, compte):
        headers_ada, _ = compte
        moyen = client.post("/compte/paiements", json=CARTE, headers=headers_ada).json()

        headers_bob, _ = auth_header(email="bob@test.fr")
        res = client.post(f"/compte/paiements/{moyen['id']}/defaut", headers=headers_bob)

        assert res.status_code == 404

    def test_les_routes_sont_fermees_sans_session(self, client):
        """Balayage exhaustif : une route ajoutee sans garde se voit ici.

        `client.get` n'accepte pas de corps, contrairement aux autres verbes -
        d'ou `client.request`, qui les traite tous de la meme facon.
        """
        for methode, chemin in [
            ("GET", "/compte/paiements"),
            ("POST", "/compte/paiements"),
            ("PATCH", "/compte/profil"),
            ("POST", "/compte/mot-de-passe"),
            ("POST", "/compte/email"),
            ("POST", "/compte/paiements/1/defaut"),
            ("DELETE", "/compte/paiements/1"),
        ]:
            res = client.request(methode, chemin, json={})
            assert res.status_code in (401, 403), f"{methode} {chemin} ouvert : {res.status_code}"


class TestPaiementAvecCarteEnregistree:
    """Une carte qu'on ne peut pas utiliser au paiement est un decor.

    C'est le defaut que ces tests empechent de revenir : la fonctionnalite
    existait de bout en bout - modele, routes, ecran - sans que le tunnel
    d'achat sache s'en servir.
    """

    def test_paie_avec_une_carte_enregistree(self, client, db_session, compte, product):
        headers, _ = compte
        moyen = client.post("/compte/paiements", json=CARTE, headers=headers).json()

        res = client.post(
            "/orders/checkout",
            json={**checkout_payload(product.id), "payment_method_id": moyen["id"]},
            headers=headers,
        )

        assert res.status_code == 201
        commande = db_session.query(models.Order).one()
        assert commande.payment_ref

    def test_on_ne_paie_pas_avec_la_carte_d_un_autre(
        self, client, db_session, auth_header, compte, product
    ):
        """LE controle qui compte. Le filtre sur le proprietaire est dans la
        requete, pas dans un test qui suit : il n'y a rien a oublier."""
        headers_ada, _ = compte
        moyen = client.post("/compte/paiements", json=CARTE, headers=headers_ada).json()

        headers_bob, _ = auth_header(email="bob@test.fr")
        res = client.post(
            "/orders/checkout",
            json={**checkout_payload(product.id), "payment_method_id": moyen["id"]},
            headers=headers_bob,
        )

        # 404 et non 403 : un 403 confirmerait que la carte existe.
        assert res.status_code == 404
        assert db_session.query(models.Order).count() == 0

    def test_un_invite_ne_peut_pas_designer_de_carte(self, client, product):
        res = client.post(
            "/orders/checkout",
            json={**checkout_payload(product.id), "payment_method_id": 1},
        )
        assert res.status_code == 401

    def test_une_carte_inexistante_est_refusee(self, client, compte, product):
        headers, _ = compte
        res = client.post(
            "/orders/checkout",
            json={**checkout_payload(product.id), "payment_method_id": 99999},
            headers=headers,
        )
        assert res.status_code == 404

    def test_sans_carte_designee_le_parcours_reste_inchange(self, client, product):
        """L'invite et le client qui saisit une carte continuent de commander."""
        assert client.post("/orders/checkout", json=checkout_payload(product.id)).status_code == 201
