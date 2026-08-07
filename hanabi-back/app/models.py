from datetime import datetime, timezone

from sqlalchemy import (
    String, Integer, Boolean, ForeignKey, Text, DateTime, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


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
    # Indexe : les cohortes d'inscription et la courbe des nouveaux comptes
    # regroupent sur ce champ, et la liste du back-office trie dessus.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")


class Product(Base):
    __tablename__ = "products"
    # Filet de securite : la base refuse un stock negatif meme si le code se trompe.
    __table_args__ = (CheckConstraint("stock >= 0", name="ck_stock_non_negatif"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40), index=True)
    blurb: Mapped[str] = mapped_column(String(255))
    price_cents: Mapped[int] = mapped_column(Integer)   # prix en centimes, jamais en float
    # Cout d'achat unitaire. Sans lui, le back-office ne mesure que du chiffre
    # d'affaires, ce qui ne dit rien de ce que la boutique gagne : deux articles
    # au meme volume de ventes peuvent avoir des marges du simple au triple.
    #
    # A zero, la marge n'est pas calculee plutot qu'affichee a 100 %, faute de
    # quoi une fiche dont le cout n'a pas ete renseigne passerait pour la plus
    # rentable du catalogue.
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    featured_order: Mapped[int] = mapped_column(Integer, default=0)
    # Visuel principal. Deux formes possibles :
    #   - un motif genere cote front, "forme,couleur1,couleur2" (une trentaine
    #     de caracteres) ;
    #   - une vraie photo, en URL ou en data URI base64 de plusieurs centaines
    #     de kilo-octets.
    #
    # D'ou `Text` et non `String(60)` : ce plafond n'avait ete pense que pour le
    # motif. SQLite ignore les longueurs declarees, si bien que le defaut
    # passait inapercu en local, mais PostgreSQL les applique et aurait rejete
    # toute photo une fois le site deploye.
    art: Mapped[str] = mapped_column(Text, default="circles,#224A3F,#E4D7BF")
    # Galerie : JSON liste de visuels (motifs "shape,c1,c2" ou URLs d'images reelles)
    images: Mapped[str] = mapped_column(Text, default="[]")

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
    # Indexe : jointure de toutes les analyses par client (cohortes, RFM,
    # meilleurs acheteurs). PostgreSQL n'indexe pas les cles etrangeres de
    # lui-meme, contrairement a ce que beaucoup supposent.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )  # commande invitee possible
    email: Mapped[str] = mapped_column(String(255))
    # Indexe : presque toute requete de chiffre d'affaires filtre sur ce champ.
    status: Mapped[str] = mapped_column(
        String(20), default="paid", index=True
    )  # pending | paid | cancelled
    subtotal_cents: Mapped[int] = mapped_column(Integer)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer)
    promo_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )

    user: Mapped["User | None"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Les deux cles etrangeres sont indexees : l'analyse de panier fait une
    # auto-jointure sur `order_id`, et le palmares du catalogue regroupe sur
    # `product_id`. Sans index, PostgreSQL parcourt la table entiere a chaque
    # affichage du tableau de bord.
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))     # fige le nom au moment de la commande
    # Copie du visuel du produit au moment de la commande, pour que l'historique
    # reste fidele meme si la fiche change ensuite. Meme raison qu'au-dessus de
    # passer en `Text` : une photo n'entre pas dans 60 caracteres, et la
    # commande d'un produit illustre aurait echoue sur PostgreSQL.
    art: Mapped[str] = mapped_column(Text)
    unit_price_cents: Mapped[int] = mapped_column(Integer)  # fige le prix paye
    # Fige aussi le cout d'achat, pour la meme raison que le prix : la marge
    # d'une commande passee doit rester celle qu'elle a reellement degagee. La
    # recalculer a partir du cout courant reecrirait l'histoire au premier
    # changement de tarif fournisseur, et ferait bouger le resultat des mois
    # deja clos.
    unit_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    qty: Mapped[int] = mapped_column(Integer)

    order: Mapped["Order"] = relationship(back_populates="items")


class Review(Base):
    __tablename__ = "reviews"
    # Un seul avis par produit et par utilisateur.
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_avis_unique"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(120))
    rating: Mapped[int] = mapped_column(Integer)  # 1 a 5
    text: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # achat reel constate
    approved: Mapped[bool] = mapped_column(Boolean, default=True)   # moderation
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    product: Mapped["Product"] = relationship(back_populates="reviews")
    user: Mapped["User | None"] = relationship(back_populates="reviews")


class ProductView(Base):
    """Consultation d'une fiche produit.

    Une ligne par ouverture de fiche, et non un compteur incremente sur le
    produit : sans la date, on ne peut repondre ni « quels articles montent
    cette semaine » ni « quel est le taux de conversion du mois », qui sont
    justement les questions que le tableau de bord doit trancher. Un compteur
    unique repond a « combien depuis toujours », et rien d'autre.

    Aucune adresse IP ni empreinte de navigateur n'est conservee : le
    rapprochement avec un compte, quand il existe, suffit aux analyses menees
    ici, et collecter davantage exigerait une base legale qu'un site vitrine
    n'a pas. `user_id` est donc nul pour un visiteur non connecte, et la ligne
    reste alors strictement anonyme.
    """

    __tablename__ = "product_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    # Indexe : toutes les series temporelles du back-office filtrent la-dessus,
    # et la table est de loin la plus volumineuse du schema.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, index=True
    )


class StockAlert(Base):
    """Demande d'alerte retour en stock sur un produit epuise."""
    __tablename__ = "stock_alerts"
    __table_args__ = (UniqueConstraint("product_id", "email", name="uq_alerte_unique"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Subscriber(Base):
    """Adresse inscrite aux annonces de series.

    Le RGPD demande de pouvoir prouver le consentement et d'y mettre fin aussi
    facilement qu'on l'a donne : on conserve donc la date d'inscription et la
    langue de la personne, et la desinscription se marque ici plutot que de
    supprimer la ligne - une adresse effacee se reinscrirait au premier
    formulaire, ce qui reviendrait a ignorer le retrait du consentement.
    """

    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    lang: Mapped[str] = mapped_column(String(5), default="fr")
    unsubscribed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)