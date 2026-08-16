import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .. import emails, idempotency, models, outbox, payments, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_optional_user
from ..pricing import quote

log = logging.getLogger("hanabi.commandes")

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/quote", response_model=schemas.QuoteOut)
def get_quote(data: schemas.QuoteIn, db: Session = Depends(get_db)):
    """Recalcule le panier cote serveur (sous-total, remise, port, total)."""
    return quote(db, data.items, data.promo_code)


@router.post("/checkout", response_model=schemas.OrderOut, status_code=201)
def checkout(
    data: schemas.CheckoutIn,
    reponse: Response,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
    idempotency_key: str | None = Header(default=None, alias=idempotency.EN_TETE),
):
    """Cree la commande : stock, paiement, courriel, le tout ou rien.

    L'ORDRE DES ETAPES N'EST PAS ARBITRAIRE. Le stock est pris avant le
    paiement : reserver ce qu'on vend evite de debiter quelqu'un pour un article
    parti entre-temps, et un refus rend le stock par simple annulation de la
    transaction. Le courriel est inscrit en file dans cette meme transaction,
    donc il existe si et seulement si la commande existe.

    REJOUABLE SANS DOMMAGE. Avec un en-tete `Idempotency-Key`, un double-clic ou
    un reessai sur delai depasse rend la reponse du premier appel au lieu de
    creer une seconde commande. L'en-tete est facultatif - les clients existants
    continuent de fonctionner - mais la boutique l'envoie systematiquement.
    """
    # Carte enregistree : on remonte au jeton, apres avoir verifie qu'elle
    # appartient au demandeur. Le filtre sur `user_id` est DANS la requete et non
    # dans un test qui suivrait - c'est ce qui rend impossible de payer avec la
    # carte d'un autre en devinant un identifiant.
    jeton_paiement = data.payment_token
    if data.payment_method_id is not None:
        if user is None:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Il faut etre connecte pour utiliser une carte enregistree.",
            )
        moyen = db.scalar(
            select(models.PaymentMethod).where(
                models.PaymentMethod.id == data.payment_method_id,
                models.PaymentMethod.user_id == user.id,
            )
        )
        if moyen is None:
            # 404 et non 403 : un 403 confirmerait que la carte existe.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Moyen de paiement introuvable.")
        jeton_paiement = moyen.jeton

    # Refus AVANT toute ecriture : inutile de prendre du stock pour une commande
    # qu'on va rejeter. Le schema declare le champ obligatoire, donc son absence
    # est deja un 422 ; ce controle vise la valeur `false`, qu'un client pourrait
    # envoyer en contournant la case a cocher.
    if not data.cgv_acceptees:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Les conditions generales de vente doivent etre acceptees.",
        )

    cle = idempotency.valider(idempotency_key)
    trace = None
    if cle:
        try:
            trace = idempotency.reserver(
                db, cle, "orders.checkout", jsonable_encoder(data)
            )
        except idempotency.Rejeu as rejeu:
            return rejeu.reponse()

    pricing = quote(db, data.items, data.promo_code)

    try:
        # --- 1. Stock : decrement atomique -------------------------------
        # `UPDATE ... WHERE stock >= qty` : si `rowcount` vaut 0, le stock etait
        # insuffisant. Correct en concurrence - deux acheteurs sur le dernier
        # article - sans verrou explicite, et identique sur SQLite et PostgreSQL.
        # La contrainte `CHECK (stock >= 0)` du modele reste en filet dernier.
        for line in pricing["lines"]:
            res = db.execute(
                update(models.Product)
                .where(models.Product.id == line.product_id, models.Product.stock >= line.qty)
                .values(stock=models.Product.stock - line.qty)
            )
            if res.rowcount == 0:
                db.rollback()
                raise HTTPException(status.HTTP_409_CONFLICT, f"Stock insuffisant pour {line.name}.")

        order = models.Order(
            number=payments.nouvelle_reference_commande(),
            user_id=user.id if user else None,
            email=str(data.email),
            status="paid",
            subtotal_cents=pricing["subtotal_cents"],
            discount_cents=pricing["discount_cents"],
            shipping_cents=pricing["shipping_cents"],
            total_cents=pricing["total_cents"],
            promo_code=pricing["promo"].code if pricing["promo"] else None,
            # La VERSION est enregistree, pas un booleen : les conditions
            # changent, et savoir qu'une case a ete cochee ne dit pas ce qui a
            # ete accepte.
            cgv_version=settings.CGV_VERSION,
            cgv_acceptees_le=models.now_utc(),
        )
        db.add(order)
        db.flush()  # recupere order.id

        lignes = []
        for line in pricing["lines"]:
            p = db.get(models.Product, line.product_id)
            article = models.OrderItem(
                order_id=order.id, product_id=p.id, name=p.name, art=p.art,
                unit_price_cents=line.unit_price_cents,
                # Fige le cout d'achat du moment, comme le prix paye.
                unit_cost_cents=p.cost_cents,
                qty=line.qty,
            )
            db.add(article)
            lignes.append(article)

        # --- 2. Paiement --------------------------------------------------
        # Simule : aucun argent ne circule (voir `payments.py`). L'etape existe
        # parce qu'elle change la nature des garde-fous autour - rejouer une
        # insertion est benin, rejouer un debit ne l'est pas.
        try:
            autorisation = payments.autoriser(
                jeton_paiement, pricing["total_cents"], order.number
            )
        except payments.PaiementRefuse as refus:
            # Refus franc : rien n'a ete debite, le stock est rendu par
            # l'annulation, et le client peut reessayer sans risque.
            db.rollback()
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, refus.motif) from refus
        except payments.PaiementIndecis:
            # Issue INCONNUE : le debit a peut-etre eu lieu.
            #
            # On ne peut ni confirmer - ce serait livrer un paiement non prouve -
            # ni annuler : annuler oublierait un debit possible, et rendrait le
            # stock alors qu'on l'a peut-etre deja vendu. La commande est donc
            # CONSERVEE en attente, avec son stock retenu, et sera rapprochee du
            # prestataire plus tard.
            #
            # Une premiere version annulait tout en invitant a reessayer avec la
            # meme cle. C'etait une promesse creuse : le `rollback` emportait
            # aussi la ligne d'idempotence, qui vit dans la meme transaction.
            # La cle disparaissait, le reessai repartait de zero, et le second
            # debit qu'on pretendait empecher devenait possible. Tout committer
            # ensemble est ce qui rend la garantie reelle.
            order.status = "pending"
            log.error(
                "paiement indecis : commande en attente de rapprochement",
                extra={"commande": order.number, "total_cents": order.total_cents},
            )
            if trace is not None:
                corps = json.dumps(jsonable_encoder(schemas.OrderOut.model_validate(order)))
                idempotency.conclure(db, trace, 202, corps)
            db.commit()
            db.refresh(order)
            # 202 : recue, pas encore confirmee. Aucun courriel de confirmation
            # n'est inscrit - il n'y a rien a confirmer tant que le paiement
            # n'est pas etabli.
            reponse.status_code = status.HTTP_202_ACCEPTED
            return order

        order.payment_ref = autorisation.reference

        # --- 3. Courriel : inscrit, pas envoye ----------------------------
        # Meme transaction que la commande : s'il y a commande, il y a courriel.
        # La remise a lieu ensuite, en tache de fond, et une panne du relais ne
        # peut donc plus faire echouer un achat deja paye.
        sujet, texte, html = emails.confirmation_commande(order, lignes)
        outbox.deposer(db, str(data.email), sujet, texte, html)

        if trace is not None:
            corps = json.dumps(jsonable_encoder(schemas.OrderOut.model_validate(order)))
            idempotency.conclure(db, trace, 201, corps)

        db.commit()
        db.refresh(order)
        log.info(
            "commande creee",
            extra={"numero": order.number, "total_cents": order.total_cents,
                   "paiement": autorisation.reference},
        )
        if cle:
            reponse.headers["Idempotent-Replay"] = "false"
        return order
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        log.exception("echec du traitement de la commande")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Echec du traitement de la commande.")


@router.get("", response_model=list[schemas.OrderOut])
def my_orders(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )
    return orders


@router.get("/{number}", response_model=schemas.OrderOut)
def get_order(number: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    order = db.query(models.Order).filter(models.Order.number == number).first()
    if order is None or order.user_id != user.id:
        raise HTTPException(404, "Commande introuvable.")
    return order
