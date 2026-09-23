"""Droits des personnes : portabilité (art. 20) et effacement (art. 17).

L'effacement anonymise au lieu de supprimer : le Code de commerce impose de
garder dix ans les pièces comptables, ce que prévoit l'article 17-3-b. Les
commandes gardent date, montants et lignes, sans nom, adresse ni courriel.

Supprimés : moyens de paiement, jetons, alertes de stock, abonnement, courriels
en file. Le texte des avis reste en ligne sous un auteur anonyme ; un nom écrit
dans un avis se retire sur demande.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from . import models

log = logging.getLogger("hanabi.rgpd")

#: Domaine réservé (RFC 2606), jamais attribué
DOMAINE_ANONYME = "anonyme.invalid"

#: Auteur affiché sur les avis conservés
NOM_ANONYME = "Client supprimé"

#: Valeur que bcrypt ne produit jamais : `verify_password` échoue toujours
CONDENSAT_INUTILISABLE = "!compte-anonymise"

#: Formule à recopier pour confirmer l'effacement
FORMULE_CONFIRMATION = "SUPPRIMER MON COMPTE"


def exporter(db: Session, user: models.User) -> dict:
    """Tout ce que la boutique détient sur la personne, en JSON lisible.

    Les moyens de paiement sortent tels qu'en base, sans le jeton du prestataire.
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
        select(models.Subscriber).where(func.lower(models.Subscriber.email) == user.email.lower())
    )

    alertes = db.scalars(
        select(models.StockAlert).where(func.lower(models.StockAlert.email) == user.email.lower())
    ).all()

    return {
        "_a_propos": {
            "genere_le": datetime.now(timezone.utc).isoformat(),
            "fondement": "Article 20 du RGPD : droit à la portabilité des données",
            "contenu": (
                "L'intégralité des données que la boutique détient sur ce compte. "
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
                "livraison": {
                    "nom": c.ship_name,
                    "adresse": c.ship_addr,
                    "code_postal": c.ship_cp,
                    "ville": c.ship_city,
                },
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
                "note": "La boutique ne conserve ni numéro complet ni cryptogramme.",
            }
            for m in moyens
        ],
        "navigation": {
            "fiches_consultees": nb_vues,
            "note": (
                "Seul le nombre est donné : chaque consultation est un horodatage "
                "associé à un produit, sans autre contenu."
            ),
        },
        "annonces": {
            "inscrit": abonnement is not None and not abonnement.unsubscribed,
            "inscrit_le": (
                models.as_utc(abonnement.created_at).isoformat() if abonnement else None
            ),
        },
        "alertes_de_retour_en_stock": [
            {
                "produit_id": a.product_id,
                "demandee_le": models.as_utc(a.created_at).isoformat(),
                "envoyee": a.notified,
            }
            for a in alertes
        ],
    }


def anonymiser(db: Session, user: models.User) -> dict:
    """Efface ce qui identifie la personne et rend le bilan. Ne valide pas la transaction.

    L'appelant valide, pour une opération tout ou rien.
    """
    identifiant = user.id
    ancienne_adresse = user.email.lower()
    bilan = {}

    # --- Supprimé ---
    bilan["moyens_de_paiement"] = db.execute(
        delete(models.PaymentMethod).where(models.PaymentMethod.user_id == identifiant)
    ).rowcount
    bilan["jetons"] = db.execute(
        delete(models.Token).where(models.Token.user_id == identifiant)
    ).rowcount
    # Comparaisons insensibles à la casse : des adresses ont été enregistrées
    # telles que saisies avant la mise en minuscules
    bilan["alertes_de_stock"] = db.execute(
        delete(models.StockAlert).where(func.lower(models.StockAlert.email) == ancienne_adresse)
    ).rowcount
    bilan["inscriptions_annonces"] = db.execute(
        delete(models.Subscriber).where(func.lower(models.Subscriber.email) == ancienne_adresse)
    ).rowcount
    bilan["courriels_en_file"] = db.execute(
        delete(models.OutboxEmail).where(
            func.lower(models.OutboxEmail.destinataire) == ancienne_adresse
        )
    ).rowcount

    # --- Conservé, délié ---
    bilan["commandes_anonymisees"] = db.execute(
        update(models.Order)
        .where(models.Order.user_id == identifiant)
        .values(
            email=_adresse_anonyme(identifiant),
            ship_name=None, ship_addr=None, ship_cp=None, ship_city=None,
        )
    ).rowcount

    bilan["avis_anonymises"] = db.execute(
        update(models.Review)
        .where(models.Review.user_id == identifiant)
        .values(author_name=NOM_ANONYME)
    ).rowcount

    # Le volume d'audience reste, sans lien avec le compte
    bilan["consultations_deliees"] = db.execute(
        update(models.ProductView)
        .where(models.ProductView.user_id == identifiant)
        .values(user_id=None)
    ).rowcount

    # --- Le compte ---
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
    # Révoque aussi les jetons déjà émis
    user.token_version = int(user.token_version or 0) + 1

    # L'ancienne adresse n'est pas journalisée
    log.warning("compte anonymise", extra={"compte": identifiant, **bilan})
    return bilan


def _adresse_anonyme(identifiant: int) -> str:
    """Adresse de remplacement unique (contrainte de colonne) et non routable."""
    return f"supprime-{identifiant}@{DOMAINE_ANONYME}"
