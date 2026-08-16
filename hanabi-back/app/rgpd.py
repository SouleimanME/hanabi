"""Droits des personnes : portabilite (art. 20) et effacement (art. 17).

POURQUOI CE N'EST PAS UN `DELETE`.

Effacer la ligne d'un client detruirait aussi ses commandes, or le Code de
commerce impose de conserver dix ans les pieces comptables. Le RGPD le prevoit
explicitement : l'article 17-3-b ecarte le droit a l'effacement lorsqu'un
traitement est necessaire au respect d'une obligation legale. Les deux textes ne
s'opposent donc pas - ils delimitent ce qu'il faut effacer et ce qu'il faut
garder.

On ANONYMISE : tout ce qui identifie une personne disparait, tout ce qui fait
foi comptablement reste. Une commande conserve sa date, ses montants et ses
lignes ; elle ne conserve plus de nom, d'adresse ni de courriel. Ce qui subsiste
n'est plus une donnee personnelle, et sort donc du champ du reglement.

CE QUI DISPARAIT VRAIMENT, en revanche, est tout ce qu'aucune loi n'oblige a
garder : moyens de paiement, jetons, alertes de stock, inscription aux annonces,
courriels en file. Rien de tout cela n'a de valeur probante.

L'OPERATION EST IRREVERSIBLE, et c'est le but. Une « corbeille » d'ou l'on
pourrait restaurer un compte ne serait pas un effacement.

LIMITE ASSUMEE : le TEXTE des avis est conserve, seul l'auteur est anonymise.
Un avis parle d'un produit et les autres clients s'y fient ; le supprimer
appauvrirait une information collective. Si quelqu'un y a ecrit son nom, aucune
analyse automatique ne peut le savoir - la suppression sur demande reste alors
la voie, et c'est ce que dit le message rendu a l'appelant.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from . import models

log = logging.getLogger("hanabi.rgpd")

#: Domaine reserve par la RFC 2606 : il ne peut etre attribue a personne, donc
#: aucune adresse anonymisee ne risque de joindre un vrai destinataire.
DOMAINE_ANONYME = "anonyme.invalid"

#: Nom affiche a la place du vrai, sur les avis conserves.
NOM_ANONYME = "Client supprime"

#: Valeur mise a la place du condensat. Elle ne peut correspondre a aucun mot de
#: passe : bcrypt ne produit jamais cette chaine, donc `verify_password` echoue
#: toujours. Le compte devient inaccessible sans qu'on ait a ajouter un drapeau
#: que chaque route devrait ensuite penser a verifier.
CONDENSAT_INUTILISABLE = "!compte-anonymise"

#: Formule a recopier pour confirmer un effacement. En francais et en
#: majuscules : elle doit etre lue, pas devinee, et un simple « OUI » se tape
#: sans y penser.
FORMULE_CONFIRMATION = "SUPPRIMER MON COMPTE"


def exporter(db: Session, user: models.User) -> dict:
    """Rassemble tout ce que la boutique detient sur une personne.

    Format JSON, lisible par une machine ET par un humain : l'article 20 exige
    un format « structure, couramment utilise et lisible par machine », et la
    personne doit pouvoir comprendre ce qu'elle recoit sans outil.

    Les moyens de paiement figurent dans l'export sous la forme qu'ils ont en
    base - reseau, quatre derniers chiffres, expiration. Le jeton du prestataire
    en est exclu : il n'est pas une donnee sur la personne mais un moyen de
    debiter, et l'exporter reviendrait a le mettre en circulation.
    """
    commandes = db.scalars(
        select(models.Order)
        .where(models.Order.user_id == user.id)
        .order_by(models.Order.created_at)
    ).all()

    avis = db.scalars(
        select(models.Review).where(models.Review.user_id == user.id)
    ).all()

    moyens = db.scalars(
        select(models.PaymentMethod).where(models.PaymentMethod.user_id == user.id)
    ).all()

    vues = db.scalar(
        select(models.ProductView)
        .where(models.ProductView.user_id == user.id)
        .with_only_columns(models.ProductView.id)
        .limit(1)
    )
    nb_vues = (
        db.query(models.ProductView).filter(models.ProductView.user_id == user.id).count()
        if vues is not None
        else 0
    )

    abonnement = db.scalar(
        select(models.Subscriber).where(models.Subscriber.email == user.email.lower())
    )

    return {
        "_a_propos": {
            "genere_le": datetime.now(timezone.utc).isoformat(),
            "fondement": "Article 20 du RGPD - droit a la portabilite des donnees",
            "contenu": (
                "L'integralite des donnees que la boutique detient sur ce compte. "
                "Les montants sont en centimes."
            ),
        },
        "compte": {
            "identifiant": user.id,
            "nom": user.name,
            "email": user.email,
            "email_confirme": user.email_verified,
            "civilite": user.civility,
            "date_de_naissance": user.birthdate,
            "telephone": user.phone,
            "adresse": user.addr,
            "complement_adresse": user.addr_extra,
            "code_postal": user.cp,
            "ville": user.city,
            "inscrit_le": models.as_utc(user.created_at).isoformat(),
        },
        "commandes": [
            {
                "numero": c.number,
                "date": models.as_utc(c.created_at).isoformat(),
                "statut": c.status,
                "email_de_commande": c.email,
                "sous_total_cents": c.subtotal_cents,
                "remise_cents": c.discount_cents,
                "livraison_cents": c.shipping_cents,
                "total_cents": c.total_cents,
                "code_promo": c.promo_code,
                "articles": [
                    {
                        "produit": a.name,
                        "quantite": a.qty,
                        "prix_unitaire_cents": a.unit_price_cents,
                    }
                    for a in c.items
                ],
            }
            for c in commandes
        ],
        "avis": [
            {
                "date": models.as_utc(a.created_at).isoformat(),
                "produit_id": a.product_id,
                "note": a.rating,
                "texte": a.text,
                "achat_verifie": a.verified,
            }
            for a in avis
        ],
        "moyens_de_paiement": [
            {
                "reseau": m.reseau,
                "quatre_derniers_chiffres": m.quatre_derniers,
                "expiration": f"{m.exp_mois:02d}/{m.exp_annee}",
                "libelle": m.libelle,
                "par_defaut": m.defaut,
                # Le numero complet n'est PAS ici parce qu'il n'est nulle part :
                # la boutique ne l'a jamais detenu.
                "note": "La boutique ne conserve ni numero complet ni cryptogramme.",
            }
            for m in moyens
        ],
        "navigation": {
            "fiches_consultees": nb_vues,
            "note": (
                "Seul le nombre est donne : chaque consultation est un horodatage "
                "associe a un produit, sans autre contenu."
            ),
        },
        "annonces": {
            "inscrit": abonnement is not None and not abonnement.unsubscribed,
            "inscrit_le": (
                models.as_utc(abonnement.created_at).isoformat() if abonnement else None
            ),
        },
    }


def anonymiser(db: Session, user: models.User) -> dict:
    """Efface tout ce qui identifie la personne. NE VALIDE PAS la transaction.

    L'appelant valide, pour que l'operation soit tout ou rien : une
    anonymisation a moitie faite laisserait des donnees personnelles derriere un
    compte declare supprime, ce qui est pire que de n'avoir rien fait.

    Rend le detail de ce qui a ete touche - l'article 17 demande de pouvoir
    rendre compte de l'effacement, et un simple « c'est fait » ne s'audite pas.
    """
    identifiant = user.id
    ancienne_adresse = user.email.lower()
    bilan = {}

    # --- Ce qui disparait sans condition -------------------------------
    # Aucun de ces enregistrements n'a de valeur probante ni d'obligation de
    # conservation.
    bilan["moyens_de_paiement"] = db.execute(
        delete(models.PaymentMethod).where(models.PaymentMethod.user_id == identifiant)
    ).rowcount
    bilan["jetons"] = db.execute(
        delete(models.Token).where(models.Token.user_id == identifiant)
    ).rowcount
    bilan["alertes_de_stock"] = db.execute(
        delete(models.StockAlert).where(models.StockAlert.email == ancienne_adresse)
    ).rowcount
    bilan["inscriptions_annonces"] = db.execute(
        delete(models.Subscriber).where(models.Subscriber.email == ancienne_adresse)
    ).rowcount
    # Les courriels en file portent l'adresse ET souvent le detail d'une
    # commande. Ceux deja partis ne sont plus rattrapables ; ceux qui restent
    # n'ont plus de destinataire legitime.
    bilan["courriels_en_file"] = db.execute(
        delete(models.OutboxEmail).where(models.OutboxEmail.destinataire == ancienne_adresse)
    ).rowcount

    # --- Ce qui reste, prive de tout lien avec une personne ------------
    # Les commandes sont conservees pour l'obligation comptable, mais elles ne
    # portent plus d'adresse.
    bilan["commandes_anonymisees"] = db.execute(
        update(models.Order)
        .where(models.Order.user_id == identifiant)
        .values(email=_adresse_anonyme(identifiant))
    ).rowcount

    # Les avis gardent leur texte - il parle d'un produit, et les autres clients
    # s'y fient - mais plus leur auteur.
    bilan["avis_anonymises"] = db.execute(
        update(models.Review)
        .where(models.Review.user_id == identifiant)
        .values(author_name=NOM_ANONYME)
    ).rowcount

    # Les consultations deviennent anonymes plutot que de disparaitre : leur
    # volume nourrit l'audience du tableau de bord, et une fois deliees d'un
    # compte elles ne designent plus personne.
    bilan["consultations_deliees"] = db.execute(
        update(models.ProductView)
        .where(models.ProductView.user_id == identifiant)
        .values(user_id=None)
    ).rowcount

    # --- Le compte lui-meme --------------------------------------------
    user.name = NOM_ANONYME
    user.email = _adresse_anonyme(identifiant)
    user.password_hash = CONDENSAT_INUTILISABLE
    user.civility = None
    user.birthdate = None
    user.phone = None
    user.addr = None
    user.addr_extra = None
    user.cp = None
    user.city = None
    user.email_verified = False
    user.anonymise_le = models.now_utc()

    # L'ancienne adresse n'apparait PAS dans le journal : consigner ce qu'on
    # vient d'effacer viderait l'operation de son sens.
    log.warning("compte anonymise", extra={"compte": identifiant, **bilan})
    return bilan


def _adresse_anonyme(identifiant: int) -> str:
    """Adresse de remplacement, unique et non routable.

    Unique parce que la colonne l'exige : deux comptes anonymises entreraient
    sinon en collision. Non routable parce que `.invalid` est reserve par la
    RFC 2606 et ne sera jamais attribue - un courriel envoye par erreur ne
    partira nulle part.
    """
    return f"supprime-{identifiant}@{DOMAINE_ANONYME}"
