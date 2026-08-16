"""Droits des personnes : portabilite (art. 20) et effacement (art. 17).

Une fonctionnalite juridique se teste par ses GARANTIES, pas par ses appels.
Trois sont verifiees ici, et la deuxieme est la plus difficile :

  1. l'export contient tout ce qu'on detient ;
  2. apres effacement, plus AUCUNE trace de la personne ne subsiste - et le test
     le verifie en balayant toutes les tables, pas en cochant celles auxquelles
     on a pense ;
  3. ce que la loi oblige a garder est bel et bien garde.
"""
import pytest

from app import models, rgpd

from antibot_helper import solve_antibot
from test_orders import checkout_payload


MOT_DE_PASSE = "Correct-Cheval-Pile-9"
CARTE = {"reseau": "visa", "quatre_derniers": "4242", "exp_mois": 12, "exp_annee": 2030}


@pytest.fixture
def compte(client, auth_header):
    headers, user = auth_header(email="ada@test.fr", password=MOT_DE_PASSE)
    return headers, user


@pytest.fixture
def compte_garni(client, db_session, compte, product):
    """Un compte avec de tout : commande, avis, carte, alerte, abonnement."""
    headers, user = compte
    user.phone = "0612345678"
    user.addr = "12 rue des Erables"
    user.cp = "75011"
    user.city = "Paris"
    db_session.commit()

    client.post("/compte/paiements", json=CARTE, headers=headers)
    client.post("/orders/checkout", json=checkout_payload(product.id, email="ada@test.fr"), headers=headers)
    client.post(
        f"/products/{product.id}/reviews",
        json={"rating": 5, "text": "Très beau bol, livraison rapide.", "antibot": solve_antibot("review")},
        headers=headers,
    )
    client.post(
        "/newsletter/subscribe",
        json={"email": "ada@test.fr", "lang": "fr", "antibot": solve_antibot("subscribe")},
    )
    db_session.commit()
    return headers, user


class TestExport:
    def test_rend_les_donnees_du_compte(self, client, compte_garni):
        headers, _ = compte_garni
        res = client.post("/compte/export", json={"password": MOT_DE_PASSE}, headers=headers)

        assert res.status_code == 200
        corps = res.json()
        assert corps["compte"]["email"] == "ada@test.fr"
        assert corps["compte"]["ville"] == "Paris"
        assert corps["compte"]["telephone"] == "0612345678"

    def test_rend_l_historique_complet(self, client, compte_garni):
        headers, _ = compte_garni
        corps = client.post(
            "/compte/export", json={"password": MOT_DE_PASSE}, headers=headers
        ).json()

        assert len(corps["commandes"]) == 1
        assert corps["commandes"][0]["articles"]
        assert len(corps["avis"]) == 1
        assert len(corps["moyens_de_paiement"]) == 1

    def test_n_expose_jamais_le_jeton_de_paiement(self, client, compte_garni):
        """Ce n'est pas une donnee SUR la personne mais un moyen de la debiter :
        l'exporter reviendrait a le mettre en circulation."""
        headers, _ = compte_garni
        corps = client.post("/compte/export", json={"password": MOT_DE_PASSE}, headers=headers).text

        assert "pm_" not in corps
        assert "jeton" not in corps

    def test_annonce_son_fondement(self, client, compte):
        """Une personne qui recoit ses donnees doit comprendre a quel titre."""
        headers, _ = compte
        corps = client.post(
            "/compte/export", json={"password": MOT_DE_PASSE}, headers=headers
        ).json()

        assert "20" in corps["_a_propos"]["fondement"]

    def test_exige_le_mot_de_passe(self, client, compte):
        """Un export rassemble en un fichier ce que le site ne montre que par
        fragments : c'est ce qu'un poste laisse ouvert permettrait d'emporter."""
        headers, _ = compte
        res = client.post("/compte/export", json={"password": "pas-le-bon"}, headers=headers)

        assert res.status_code == 403

    def test_ferme_sans_session(self, client):
        assert client.post("/compte/export", json={"password": "x"}).status_code in (401, 403)


class TestEffacement:
    def _supprimer(self, client, headers, mot_de_passe=MOT_DE_PASSE, formule=None):
        return client.post(
            "/compte/suppression",
            json={
                "password": mot_de_passe,
                "confirmation": formule if formule is not None else rgpd.FORMULE_CONFIRMATION,
            },
            headers=headers,
        )

    def test_efface_le_compte(self, client, db_session, compte_garni):
        headers, user = compte_garni
        res = self._supprimer(client, headers)

        assert res.status_code == 200
        db_session.refresh(user)
        assert user.name == rgpd.NOM_ANONYME
        assert user.email.endswith(rgpd.DOMAINE_ANONYME)
        assert user.anonymise_le is not None

    def test_AUCUNE_TRACE_DE_LA_PERSONNE_NE_SUBSISTE(self, client, db_session, compte_garni):
        """LA garantie du droit a l'effacement, verifiee par BALAYAGE.

        On ne coche pas les tables auxquelles on a pense : on parcourt toutes
        les colonnes textuelles de tout le schema et on cherche les valeurs
        personnelles. Une table ajoutee plus tard et oubliee dans
        `rgpd.anonymiser` fera echouer ce test sans qu'on ait rien a y ajouter.
        """
        headers, _ = compte_garni
        personnelles = ["ada@test.fr", "0612345678", "12 rue des Erables", "75011"]

        self._supprimer(client, headers)

        trouvailles = []
        for table in models.Base.metadata.sorted_tables:
            colonnes = [c for c in table.columns if hasattr(c.type, "length")]
            if not colonnes:
                continue
            for ligne in db_session.execute(table.select()).mappings():
                for colonne in colonnes:
                    valeur = ligne.get(colonne.name)
                    if not isinstance(valeur, str):
                        continue
                    for donnee in personnelles:
                        if donnee.lower() in valeur.lower():
                            trouvailles.append(f"{table.name}.{colonne.name} = {valeur!r}")

        assert trouvailles == [], "donnees personnelles restantes :\n" + "\n".join(trouvailles)

    def test_le_compte_devient_inaccessible(self, client, compte_garni):
        headers, _ = compte_garni
        self._supprimer(client, headers)

        res = client.post(
            "/auth/login",
            json={"email": "ada@test.fr", "password": MOT_DE_PASSE, "antibot": solve_antibot("login")},
        )
        assert res.status_code == 401

    def test_les_moyens_de_paiement_disparaissent(self, client, db_session, compte_garni):
        """Aucune loi n'oblige a les garder."""
        headers, user = compte_garni
        self._supprimer(client, headers)

        assert db_session.query(models.PaymentMethod).filter_by(user_id=user.id).count() == 0

    def test_l_inscription_aux_annonces_disparait(self, client, db_session, compte_garni):
        headers, _ = compte_garni
        self._supprimer(client, headers)

        assert db_session.query(models.Subscriber).filter_by(email="ada@test.fr").count() == 0

    def test_les_courriels_en_file_disparaissent(self, client, db_session, compte_garni):
        headers, _ = compte_garni
        self._supprimer(client, headers)

        assert db_session.query(models.OutboxEmail).filter_by(destinataire="ada@test.fr").count() == 0


class TestCeQuiDoitRester:
    """L'article 17-3-b ecarte l'effacement quand une loi impose de conserver."""

    def _supprimer(self, client, headers):
        return client.post(
            "/compte/suppression",
            json={"password": MOT_DE_PASSE, "confirmation": rgpd.FORMULE_CONFIRMATION},
            headers=headers,
        )

    def test_les_commandes_sont_conservees(self, client, db_session, compte_garni):
        """Code de commerce L123-22 : dix ans pour les pieces comptables."""
        headers, _ = compte_garni
        avant = db_session.query(models.Order).count()

        self._supprimer(client, headers)

        assert db_session.query(models.Order).count() == avant

    def test_les_montants_restent_intacts(self, client, db_session, compte_garni):
        headers, _ = compte_garni
        commande = db_session.query(models.Order).one()
        total, articles = commande.total_cents, len(commande.items)

        self._supprimer(client, headers)

        db_session.refresh(commande)
        assert commande.total_cents == total
        assert len(commande.items) == articles

    def test_le_texte_des_avis_reste_en_ligne(self, client, db_session, compte_garni):
        """Un avis parle d'un produit, et les autres clients s'y fient. Seul
        l'auteur est anonymise - la limite est annoncee dans la reponse."""
        headers, _ = compte_garni
        self._supprimer(client, headers)

        avis = db_session.query(models.Review).one()
        assert avis.text == "Très beau bol, livraison rapide."
        assert avis.author_name == rgpd.NOM_ANONYME

    def test_la_reponse_annonce_la_limite_sur_les_avis(self, client, compte_garni):
        headers, _ = compte_garni
        corps = self._supprimer(client, headers).json()

        assert "avis" in corps["note_avis"].lower()

    def test_les_consultations_restent_mais_deliees(self, client, db_session, compte_garni, product):
        """Leur volume nourrit l'audience ; deliees d'un compte, elles ne
        designent plus personne."""
        headers, user = compte_garni
        db_session.add(models.ProductView(product_id=product.id, user_id=user.id))
        db_session.commit()
        avant = db_session.query(models.ProductView).count()

        self._supprimer(client, headers)

        assert db_session.query(models.ProductView).count() == avant
        assert db_session.query(models.ProductView).filter_by(user_id=user.id).count() == 0


class TestGardeFous:
    def test_exige_le_mot_de_passe(self, client, db_session, compte):
        headers, user = compte
        res = client.post(
            "/compte/suppression",
            json={"password": "pas-le-bon", "confirmation": rgpd.FORMULE_CONFIRMATION},
            headers=headers,
        )

        assert res.status_code == 403
        db_session.refresh(user)
        assert user.anonymise_le is None

    def test_exige_la_formule_recopiee(self, client, db_session, compte):
        """Le mot de passe prouve qu'on est la ; la formule prouve qu'on a lu."""
        headers, user = compte
        res = client.post(
            "/compte/suppression",
            json={"password": MOT_DE_PASSE, "confirmation": "oui"},
            headers=headers,
        )

        assert res.status_code == 422
        db_session.refresh(user)
        assert user.anonymise_le is None

    def test_tolere_la_casse_et_les_espaces(self, client, db_session, compte):
        """Refuser « supprimer mon compte » en minuscules serait une brimade."""
        headers, user = compte
        res = client.post(
            "/compte/suppression",
            json={"password": MOT_DE_PASSE, "confirmation": "  supprimer mon compte  "},
            headers=headers,
        )

        assert res.status_code == 200
        db_session.refresh(user)
        assert user.anonymise_le is not None

    def test_un_administrateur_ne_peut_pas_s_effacer(self, client, auth_header):
        """Il fermerait la porte du back-office derriere lui."""
        headers, _ = auth_header(email="patron@test.fr", is_admin=True, password=MOT_DE_PASSE)
        res = client.post(
            "/compte/suppression",
            json={"password": MOT_DE_PASSE, "confirmation": rgpd.FORMULE_CONFIRMATION},
            headers=headers,
        )

        assert res.status_code == 409

    def test_ferme_sans_session(self, client):
        res = client.post("/compte/suppression", json={"password": "x", "confirmation": "y"})
        assert res.status_code in (401, 403)

    def test_l_ancienne_adresse_n_apparait_pas_dans_la_reponse(self, client, compte_garni):
        """Renvoyer ce qu'on vient d'effacer viderait l'operation de son sens."""
        headers, _ = compte_garni
        corps = client.post(
            "/compte/suppression",
            json={"password": MOT_DE_PASSE, "confirmation": rgpd.FORMULE_CONFIRMATION},
            headers=headers,
        ).text

        assert "ada@test.fr" not in corps


class TestAdresseDeRemplacement:
    def test_est_unique_par_compte(self, db_session):
        """Deux comptes anonymises entreraient sinon en collision sur la
        contrainte d'unicite de l'adresse."""
        assert rgpd._adresse_anonyme(1) != rgpd._adresse_anonyme(2)

    def test_utilise_un_domaine_non_routable(self):
        """`.invalid` est reserve par la RFC 2606 : un courriel envoye par
        erreur ne partira nulle part."""
        assert rgpd._adresse_anonyme(1).endswith(".invalid")
