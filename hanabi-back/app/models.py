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
    """Ramene un datetime a UTC, qu'il porte ou non un fuseau.

    Les colonnes sont declarees `DateTime(timezone=True)`, mais SQLite n'a pas
    de type date natif et ne conserve pas le fuseau : la valeur relue est naive
    alors que la meme colonne rend une valeur consciente sur PostgreSQL. Toute
    comparaison Python entre une de ces valeurs et un `datetime.now(timezone.utc)`
    leve donc un TypeError - en local et dans la suite de tests seulement, ce qui
    en fait un piege qui ne se declenche jamais la ou on l'attend.

    Une valeur naive est consideree comme etant deja en UTC, ce qui correspond a
    ce que l'application ecrit.
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
    # Adresse confirmee par un lien recu sur cette adresse.
    #
    # Le compte reste UTILISABLE sans confirmation, et c'est un choix : bloquer
    # la connexion tant que le lien n'est pas suivi transforme un courriel perdu
    # dans les indesirables en compte inaccessible, et fait fuir a l'etape la
    # plus fragile du parcours. C'est aussi ce que font la plupart des boutiques.
    # Le drapeau sert a ne pas ecrire a une adresse jamais confirmee, et a
    # exiger la confirmation le jour ou une action sensible s'ajouterait.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Date d'exercice du droit a l'effacement (RGPD art. 17). Non nul signifie
    # que la ligne ne porte plus aucune donnee personnelle : elle subsiste pour
    # que les commandes gardent leur rattachement comptable, rien de plus.
    #
    # Le champ ne sert PAS a interdire la connexion - c'est le condensat rendu
    # inutilisable qui s'en charge, et une garde qui repose sur un drapeau est
    # une garde que chaque nouvelle route doit penser a poser. Il sert a
    # l'affichage et a l'audit : savoir qu'un compte a ete efface, et quand.
    anonymise_le: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    # Reference d'autorisation rendue par le prestataire de paiement (simule ici,
    # voir `payments.py`). Sans elle, rien ne permet de rapprocher une commande
    # d'un mouvement bancaire : c'est la premiere chose que demande un service
    # comptable, et la seule piste exploitable en cas de litige.
    payment_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # VERSION DES CONDITIONS DE VENTE acceptees au moment de commander.
    #
    # En vente a distance, l'acceptation doit pouvoir se PROUVER, et une case
    # cochee qui ne laisse aucune trace ne prouve rien. On enregistre donc la
    # version du texte, pas un simple booleen : les conditions changent, et
    # savoir qu'une personne a coche une case ne dit pas CE QU'ELLE a accepte.
    #
    # Nullable : les commandes anterieures a cette regle n'en portent pas, et
    # leur inventer une valeur serait une affirmation fausse en base.
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

class OutboxEmail(Base):
    """File d'attente des courriels a remettre.

    POURQUOI UNE TABLE PLUTOT QU'UN ENVOI DIRECT. Envoyer depuis la requete de
    commande lie deux choses qui n'ont pas la meme fiabilite : une ecriture en
    base, transactionnelle, et un appel reseau vers un tiers, qui peut etre lent
    ou indisponible. Les coudre ensemble donne deux pannes symetriques et toutes
    deux graves - soit on fait attendre l'acheteur pendant que le relais rame,
    soit une panne du relais fait echouer une commande deja payee.

    Le message est donc ECRIT DANS LA MEME TRANSACTION que la commande. S'il y a
    une commande, il y a un courriel : la garantie vient de la base, pas d'un
    espoir. Une tache de fond le remet ensuite, avec reessais espaces.

    C'est le motif « transactional outbox ». Sa limite est connue et assumee :
    la remise est au-moins-une-fois, jamais exactement-une-fois. Un envoi reussi
    dont l'ecriture du statut echoue sera rejoue. Pour une confirmation de
    commande, un doublon occasionnel est preferable a un silence.
    """

    __tablename__ = "outbox_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    destinataire: Mapped[str] = mapped_column(String(255))
    sujet: Mapped[str] = mapped_column(String(255))
    texte: Mapped[str] = mapped_column(Text)
    html: Mapped[str | None] = mapped_column(Text, nullable=True)

    # en_attente | envoye | abandonne
    #
    # Indexe conjointement a la date de prochaine tentative : la tache de fond
    # ne pose qu'une seule question, « qu'y a-t-il a envoyer maintenant », et
    # elle la pose en boucle. Sans cet index elle balaierait toute la table a
    # chaque tour, y compris les messages deja remis, dont le nombre ne fait que
    # croitre.
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
    """Trace d'une requete non rejouable, et de sa reponse.

    LE PROBLEME. Un double-clic sur « Payer », un navigateur qui rejoue une
    requete apres une coupure, un client mobile qui reessaie sur delai depasse :
    dans les trois cas la meme intention arrive deux fois. Sans garde, cela fait
    deux commandes, deux debits de stock et deux courriels pour un seul achat -
    et le client n'a rien fait de mal.

    LA REGLE. Le client tire une cle au hasard AVANT d'envoyer, et la repete a
    l'identique s'il reessaie. Le serveur enregistre la cle et la reponse qu'il a
    produite ; a la deuxieme presentation de la meme cle, il rejoue cette reponse
    sans refaire le travail.

    L'EMPREINTE de la requete est conservee avec la cle. Une meme cle presentee
    avec un corps different n'est pas un reessai mais une erreur du client -
    typiquement une cle reutilisee par megarde - et doit etre refusee plutot que
    de renvoyer la reponse d'un autre achat.

    L'unicite est portee par la BASE et non par une verification prealable :
    entre un `SELECT` qui ne trouve rien et l'`INSERT` qui suit, une seconde
    requete peut passer. C'est exactement le cas du double-clic, ou les deux
    appels partent a quelques millisecondes d'intervalle. La contrainte unique
    tranche, et le perdant traite la violation comme un reessai.
    """

    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    cle: Mapped[str] = mapped_column(String(128))
    # La cle n'est unique QUE pour un point d'entree donne : deux appels
    # differents peuvent legitimement porter la meme, et rien n'oblige un client
    # a cloisonner ses tirages.
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
    """Jeton a usage unique : verification d'adresse, reinitialisation.

    STOCKE HACHE, jamais en clair. Le raisonnement est celui des mots de passe :
    une copie de la base ne doit pas suffire a prendre la main sur des comptes.
    Un jeton de reinitialisation en clair dans une sauvegarde, c'est un acces
    administrateur a chaque compte dont le jeton n'a pas expire.

    SHA-256 sans sel ni etirement, contrairement aux mots de passe, et c'est
    voulu : un jeton fait 32 octets tires au hasard, il n'a ni motif ni
    reutilisation entre sites, et il expire en une heure. Ce qui rend bcrypt
    indispensable pour un mot de passe - sa faible entropie - n'existe pas ici,
    et la lenteur y serait payee a chaque verification sans rien acheter.

    A USAGE UNIQUE, et c'est la raison de le mettre en base plutot que de le
    signer. Un jeton signe se verifie sans etat, mais rien ne l'empeche de
    resservir tant qu'il n'a pas expire : un lien de reinitialisation reste
    alors valable une heure apres avoir change le mot de passe, y compris dans
    la boite de quelqu'un qui a eu acces au courriel. Ici, `utilise_le` ferme
    la porte des le premier usage.
    """

    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    # verification_email | reinitialisation
    usage: Mapped[str] = mapped_column(String(30), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Indexe et unique : c'est par lui qu'on retrouve la ligne, et deux jetons
    # identiques signaleraient un tirage defaillant.
    empreinte: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    utilise_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped["User"] = relationship()


class PaymentMethod(Base):
    """Moyen de paiement enregistre.

    CE QUI N'EST PAS ICI, et c'est l'essentiel : le numero de carte et le
    cryptogramme. Ni chiffres, ni chiffres masques, ni chiffres chiffres. Cette
    table contient exactement ce qu'une vraie integration conserve - de quoi
    RECONNAITRE une carte a l'ecran, et un jeton opaque emis par le prestataire
    pour la debiter. C'est ce qui maintient l'application hors du perimetre
    PCI-DSS : on ne peut pas se faire voler ce qu'on ne detient pas.

    Le jeton est simule ici, comme tout le paiement de cette boutique (voir
    `payments.py`). Sa forme et son usage sont ceux d'un vrai : le serveur ne
    sait pas le lire, il se contente de le transmettre.

    Les quatre derniers chiffres ne sont pas une donnee sensible : ils figurent
    sur tout ticket de caisse, et ne permettent ni de reconstituer un numero ni
    d'autoriser quoi que ce soit.
    """

    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # visa | mastercard | amex | unknown - tel que detecte cote client.
    reseau: Mapped[str] = mapped_column(String(20))
    quatre_derniers: Mapped[str] = mapped_column(String(4))
    exp_mois: Mapped[int] = mapped_column(Integer)
    exp_annee: Mapped[int] = mapped_column(Integer)
    # Etiquette libre : « perso », « pro ». Facultative.
    libelle: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Jeton opaque du prestataire. Unique : deux enregistrements du meme moyen
    # de paiement produiraient deux lignes indiscernables a l'ecran.
    jeton: Mapped[str] = mapped_column(String(64), unique=True)

    # Carte proposee par defaut au paiement. L'unicite n'est PAS portee par une
    # contrainte : PostgreSQL sait faire un index partiel, SQLite non, et un
    # index unique ordinaire sur (user_id, defaut) interdirait d'avoir deux
    # cartes non favorites. La regle est donc appliquee a l'ecriture, en un seul
    # endroit (voir `routers/paiements.py`).
    defaut: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped["User"] = relationship()
