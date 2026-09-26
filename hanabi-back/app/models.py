from datetime import datetime, timezone

from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, Text, DateTime, CheckConstraint, UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Ramène un datetime à UTC.

    SQLite relit les colonnes `DateTime(timezone=True)` sans fuseau, PostgreSQL
    avec : sans cette normalisation, comparer à `datetime.now(timezone.utc)` lève
    un TypeError en local seulement. Une valeur naïve est tenue pour UTC.
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    civility: Mapped[str | None] = mapped_column(String(10), nullable=True)   # M | F | N
    birthdate: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    addr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    addr_extra: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cp: Mapped[str | None] = mapped_column(String(10), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Le compte reste utilisable sans confirmation ; le drapeau évite d'écrire à
    # une adresse jamais confirmée.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Effacement RGPD (art. 17) : la ligne ne porte plus de donnée personnelle et
    # ne subsiste que pour les commandes. La connexion est bloquée par le
    # condensat inutilisable, pas par ce champ.
    anonymise_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Copié dans chaque JWT et comparé à la lecture : l'incrémenter révoque toutes
    # les sessions du compte (changement de mot de passe, effacement).
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Indexé : cohortes d'inscription, courbe des nouveaux comptes, tri du back-office
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")


class Product(Base):
    __tablename__ = "products"
    # La base refuse un stock négatif, même si le code se trompe
    __table_args__ = (CheckConstraint("stock >= 0", name="ck_stock_non_negatif"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40), index=True)
    blurb: Mapped[str] = mapped_column(String(255))
    price_cents: Mapped[int] = mapped_column(Integer)
    # Coût d'achat unitaire. À zéro, la marge n'est pas calculée (et non affichée à 100 %).
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    featured_order: Mapped[int] = mapped_column(Integer, default=0)
    # Blason "forme,tracé,fond" ou photo (URL, data URI). `Text` : PostgreSQL
    # applique les longueurs déclarées, et une photo en base64 dépasse vite.
    art: Mapped[str] = mapped_column(Text, default="torii,#E0452A,#0A0605")
    # Galerie : liste JSON de blasons ou d'images
    images: Mapped[str] = mapped_column(Text, default="[]")
    # Une ligne par usage (pièce, occasion, public) : lu par la recherche, jamais affiché
    usages: Mapped[str] = mapped_column(Text, default="")
    # Ce que montre la photo principale, pour qui ne la voit pas
    alt: Mapped[str] = mapped_column(String(300), default="")
    # {"en": {"name", "blurb", "usages", "alt"}, "es": {...}} : voir translations.py
    traductions: Mapped[str] = mapped_column(Text, default="{}")

    reviews: Mapped[list["Review"]] = relationship(back_populates="product")


class Promo(Base):
    __tablename__ = "promos"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(20))  # percent | fixed | free_shipping
    percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_subtotal_cents: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    # Indexé : PostgreSQL n'indexe pas les clés étrangères, et toutes les analyses
    # par client joignent ici. Nul pour une commande invitée.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    email: Mapped[str] = mapped_column(String(255))
    # Indexé : filtre de presque toutes les requêtes de chiffre d'affaires
    status: Mapped[str] = mapped_column(
        String(20), default="paid", index=True
    )  # pending | paid | shipped | delivered | cancelled | refunded
    subtotal_cents: Mapped[int] = mapped_column(Integer)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer)
    promo_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Adresse de livraison saisie au paiement. Nulle pour les commandes
    # antérieures à la règle ; effacée par l'anonymisation RGPD.
    ship_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ship_addr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ship_cp: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ship_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Référence d'autorisation du prestataire (simulé, voir `payments.py`), pour
    # rapprocher la commande d'un mouvement bancaire.
    payment_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Version des CGV acceptées : la preuve porte sur le texte, pas sur une case.
    # Nul pour les commandes antérieures à la règle.
    cgv_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cgv_acceptees_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )

    user: Mapped["User | None"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Indexées : auto-jointure de l'analyse de panier, regroupement du palmarès
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    # Nom, visuel, catégorie, prix et coût figés à la commande : l'historique et la
    # marge des mois clos ne bougent pas quand la fiche, son classement ou le tarif
    # fournisseur change.
    name: Mapped[str] = mapped_column(String(160))
    art: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    unit_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    qty: Mapped[int] = mapped_column(Integer)

    order: Mapped["Order"] = relationship(back_populates="items")


class Review(Base):
    __tablename__ = "reviews"
    # Un avis par produit et par utilisateur
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_avis_unique"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(120))
    rating: Mapped[int] = mapped_column(Integer)  # 1 à 5
    text: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # achat constaté
    approved: Mapped[bool] = mapped_column(Boolean, default=True)   # modération
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    product: Mapped["Product"] = relationship(back_populates="reviews")
    user: Mapped["User | None"] = relationship(back_populates="reviews")


class ProductView(Base):
    """Consultation d'une fiche produit, une ligne par ouverture (séries et conversion).

    Ni IP ni empreinte de navigateur ; `user_id` est nul pour un visiteur anonyme.
    """

    __tablename__ = "product_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    # Indexé : table la plus volumineuse, filtrée par toutes les séries temporelles
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )


class StockAlert(Base):
    """Demande d'alerte de retour en stock, servie par `restock.py` quand le stock remonte."""
    __tablename__ = "stock_alerts"
    __table_args__ = (UniqueConstraint("product_id", "email", name="uq_alerte_unique"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    # Langue de la page au moment de la demande, pour écrire dans la même
    lang: Mapped[str] = mapped_column(String(5), default="fr", server_default="fr")
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Subscriber(Base):
    """Inscrit à la lettre d'information.

    Date et langue conservées comme preuve du consentement. La désinscription se
    marque au lieu de supprimer la ligne, pour que le retrait soit respecté.
    """

    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    lang: Mapped[str] = mapped_column(String(5), default="fr")
    unsubscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class OutboxEmail(Base):
    """File des courriels à remettre (transactional outbox).

    Le message s'écrit dans la transaction de la commande ; une tâche de fond le
    remet avec des réessais espacés. Remise au moins une fois : un envoi réussi
    dont le statut n'a pas pu s'écrire sera rejoué.
    """

    __tablename__ = "outbox_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    destinataire: Mapped[str] = mapped_column(String(255))
    sujet: Mapped[str] = mapped_column(String(255))
    texte: Mapped[str] = mapped_column(Text)
    html: Mapped[str | None] = mapped_column(Text, nullable=True)

    # en_attente | envoye | abandonne ; indexé avec la prochaine tentative (voir __table_args__)
    statut: Mapped[str] = mapped_column(String(20), default="en_attente")
    tentatives: Mapped[int] = mapped_column(Integer, default=0)
    derniere_erreur: Mapped[str | None] = mapped_column(Text, nullable=True)
    prochaine_tentative: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    envoye_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_outbox_a_traiter", "statut", "prochaine_tentative"),
    )


class IdempotencyKey(Base):
    """Clé d'idempotence d'une requête non rejouable, avec la réponse produite.

    Le client tire la clé avant d'envoyer et la répète en cas de réessai ; le
    serveur rejoue la réponse enregistrée. Une même clé avec un corps différent
    (empreinte) est refusée. L'unicité repose sur la contrainte de base, pas sur
    un SELECT préalable.
    """

    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    cle: Mapped[str] = mapped_column(String(128))
    # Unique par point d'entrée seulement
    point_entree: Mapped[str] = mapped_column(String(80))
    empreinte: Mapped[str] = mapped_column(String(64))

    # en_cours | termine
    statut: Mapped[str] = mapped_column(String(20), default="en_cours")
    code_reponse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corps_reponse: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )

    __table_args__ = (
        UniqueConstraint("cle", "point_entree", name="uq_idempotence"),
    )


class Token(Base):
    """Jeton à usage unique : vérification d'adresse, réinitialisation.

    Stocké haché (SHA-256) : une copie de la base ne donne accès à aucun compte.
    Pas de bcrypt, inutile sur 32 octets aléatoires qui expirent en une heure.
    En base plutôt que signé, pour que `utilise_le` l'invalide dès le premier usage.
    """

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    # verification_email | reinitialisation
    usage: Mapped[str] = mapped_column(String(30), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    empreinte: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    utilise_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped["User"] = relationship()


class PaymentMethod(Base):
    """Moyen de paiement enregistré.

    Ni numéro ni cryptogramme, sous aucune forme : réseau, quatre derniers
    chiffres, expiration et jeton opaque du prestataire (simulé, voir
    `payments.py`). C'est ce qui garde l'application hors du périmètre PCI-DSS.
    """

    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # visa | mastercard | amex | unknown, détecté côté client
    reseau: Mapped[str] = mapped_column(String(20))
    quatre_derniers: Mapped[str] = mapped_column(String(4))
    exp_mois: Mapped[int] = mapped_column(Integer)
    exp_annee: Mapped[int] = mapped_column(Integer)
    # Étiquette libre et facultative : « perso », « pro »
    libelle: Mapped[str | None] = mapped_column(String(40), nullable=True)

    jeton: Mapped[str] = mapped_column(String(64), unique=True)

    # Une seule carte par défaut par compte. SQLite n'a pas d'index partiel : la
    # règle s'applique à l'écriture, dans `routers/compte.py`.
    defaut: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped["User"] = relationship()
