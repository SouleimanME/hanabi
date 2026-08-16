from datetime import datetime
import json

from pydantic import BaseModel, EmailStr, Field, computed_field, ConfigDict, field_validator

from .antibot import AntiBotFields


def euros(cents: int) -> float:
    return round(cents / 100, 2)


# ---------- Auth ----------
# Les formulaires publics portent un bloc `antibot` (defi resolu, pot de miel,
# horodatage signe). Voir app/antibot.py.
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    # La longueur minimale reelle est appliquee par app/passwords.py, qui refuse
    # aussi les mots de passe courants. Ici on borne seulement l'entree.
    password: str = Field(min_length=1, max_length=128)
    antibot: AntiBotFields
    civility: str | None = Field(None, pattern="^(M|F|N)$")
    birthdate: str | None = None
    phone: str | None = None
    addr: str | None = None
    addr_extra: str | None = None
    cp: str | None = None
    city: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    antibot: AntiBotFields


class UserOut(BaseModel):
    """Profil renvoye a son proprietaire (inscription, connexion, /auth/me).

    Les coordonnees collectees a l'inscription sont incluses pour que l'ecran
    « Mes informations » puisse les afficher : sans elles, le client n'avait
    aucun moyen de relire ce qu'il avait saisi. Elles restent facultatives,
    un compte cree avant leur ajout n'en porte aucune.

    Ce schema ne sert jamais a decrire un autre utilisateur : l'administration
    a le sien (AdminUserOut), et aucune route publique ne renvoie de profil.
    """

    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    civility: str | None = None
    birthdate: str | None = None
    phone: str | None = None
    addr: str | None = None
    addr_extra: str | None = None
    cp: str | None = None
    city: str | None = None
    # Permet a l'interface de proposer « renvoyer le lien » plutot que de laisser
    # deviner pourquoi rien ne s'est passe.
    email_verified: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class VerifyEmailIn(BaseModel):
    jeton: str = Field(min_length=16, max_length=128)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    jeton: str = Field(min_length=16, max_length=128)
    # Bornes de forme seulement : la politique reelle (longueur, motifs
    # courants, ressemblance avec l'adresse ou le nom) vit dans `passwords.py`
    # et s'applique ici comme a l'inscription. La dupliquer en annotation
    # produirait deux verites, dont l'une finirait par diverger.
    password: str = Field(min_length=1, max_length=200)


# ---------- Compte : modification du profil ----------
class ProfilPatch(BaseModel):
    """Champs modifiables du profil.

    TOUS FACULTATIFS, et c'est le point : l'ecran envoie ce qui a change, pas
    l'objet entier. Un formulaire qui reposte tout ecraserait avec des valeurs
    perimees les champs qu'un autre onglet vient de modifier.

    `None` signifie « ne touche pas ». Pour VIDER un champ facultatif, on envoie
    une chaine vide - la distinction est explicite dans le routeur, faute de quoi
    aucun champ ne pourrait jamais etre efface.

    L'e-mail et le mot de passe n'y figurent pas : ils changent par des routes
    dediees, parce qu'ils engagent l'acces au compte et non son contenu.
    """

    name: str | None = Field(None, min_length=2, max_length=120)
    civility: str | None = Field(None, pattern="^(M|F|N)$")
    birthdate: str | None = None
    phone: str | None = Field(None, max_length=30)
    addr: str | None = Field(None, max_length=255)
    addr_extra: str | None = Field(None, max_length=255)
    cp: str | None = Field(None, max_length=10)
    city: str | None = Field(None, max_length=120)


class ChangePasswordIn(BaseModel):
    """Changement de mot de passe par quelqu'un qui connait l'ancien.

    L'ancien est EXIGE, meme si la session prouve deja l'identite : un poste
    laisse ouvert quelques minutes suffirait autrement a verrouiller
    definitivement le proprietaire hors de son compte.
    """

    ancien: str = Field(min_length=1, max_length=200)
    nouveau: str = Field(min_length=1, max_length=200)


class ChangeEmailIn(BaseModel):
    """Changement d'adresse. Le mot de passe est exige pour la meme raison."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class MotDePasseIn(BaseModel):
    """Reconfirmation d'identite pour une action sensible."""

    password: str = Field(min_length=1, max_length=200)


class SuppressionIn(BaseModel):
    """Effacement du compte : mot de passe ET formule recopiee.

    Deux confirmations plutot qu'une. Le mot de passe prouve qu'on est bien la
    maintenant ; la formule prouve qu'on a lu ce qui va se passer. Une seule des
    deux laisserait passer soit un poste laisse ouvert, soit un clic distrait -
    et l'operation est irreversible.
    """

    password: str = Field(min_length=1, max_length=200)
    confirmation: str = Field(min_length=1, max_length=60)


# ---------- Moyens de paiement ----------
class MoyenPaiementIn(BaseModel):
    """Ce que le navigateur transmet apres avoir saisi une carte.

    AUCUN NUMERO, AUCUN CRYPTOGRAMME. Ces deux valeurs ne quittent pas la page :
    le navigateur en tire un jeton et n'envoie que de quoi reconnaitre la carte a
    l'ecran. C'est exactement le partage des roles d'une integration reelle, ou
    le jeton vient du prestataire ; ici il est simule, sa forme et son usage sont
    identiques.

    Le serveur ne fait donc PAS confiance a ces champs pour debiter - il n'a que
    le jeton pour cela. Ils ne servent qu'a l'affichage.
    """

    reseau: str = Field(pattern="^(visa|mastercard|amex|unknown)$")
    quatre_derniers: str = Field(pattern=r"^\d{4}$")
    exp_mois: int = Field(ge=1, le=12)
    # Bornes larges a dessein : une carte emise aujourd'hui peut expirer dans
    # dix ans, et refuser 2036 serait une bogue a retardement.
    exp_annee: int = Field(ge=2024, le=2099)
    libelle: str | None = Field(None, max_length=40)
    defaut: bool = False


class MoyenPaiementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reseau: str
    quatre_derniers: str
    exp_mois: int
    exp_annee: int
    libelle: str | None = None
    defaut: bool
    # Le jeton n'est jamais renvoye : il sert a debiter, et l'interface n'a
    # aucune raison de le connaitre.


# ---------- Produits ----------
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    category: str
    blurb: str
    price_cents: int
    stock: int
    is_new: bool
    featured: bool = False
    art: str
    images: list[str] = []
    rating_avg: float = 0.0
    rating_count: int = 0

    @computed_field
    @property
    def price(self) -> float:
        return euros(self.price_cents)

    @field_validator("images", mode="before")
    @classmethod
    def _parse_images(cls, v):
        # En base, images est stocke en JSON string ; on accepte string ou liste.
        if isinstance(v, str):
            try:
                return json.loads(v) if v else []
            except (ValueError, TypeError):
                return []
        return v or []


# ---------- Avis ----------
class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=3, max_length=2000)
    antibot: AntiBotFields


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author_name: str
    rating: int
    text: str
    verified: bool
    created_at: datetime


class NotifyIn(BaseModel):
    email: EmailStr
    antibot: AntiBotFields


# ---------- Annonces de series ----------
class SubscribeIn(BaseModel):
    email: EmailStr
    lang: str = Field("fr", max_length=5)
    antibot: AntiBotFields


class SubscribeOut(BaseModel):
    """Reponse a une inscription.

    `code` n'est renseigne que si l'offre de bienvenue existe et est active en
    base : promettre une remise que la caisse refusera vaut moins que ne rien
    promettre du tout.
    """

    ok: bool = True
    code: str | None = None


# ---------- Promo ----------
class PromoCheckIn(BaseModel):
    code: str
    subtotal_cents: int = Field(ge=0)


class PromoOut(BaseModel):
    code: str
    kind: str
    label: str


# ---------- Panier / Checkout ----------
class CartLineIn(BaseModel):
    product_id: int
    qty: int = Field(ge=1, le=99)


class QuoteIn(BaseModel):
    items: list[CartLineIn]
    promo_code: str | None = None


class QuoteLineOut(BaseModel):
    product_id: int
    name: str
    unit_price_cents: int
    qty: int
    line_total_cents: int


class QuoteOut(BaseModel):
    lines: list[QuoteLineOut]
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    total_cents: int
    promo: PromoOut | None = None


class ShippingIn(BaseModel):
    prenom: str
    nom: str
    adresse: str
    cp: str
    ville: str


class CheckoutIn(BaseModel):
    items: list[CartLineIn]
    email: EmailStr
    shipping: ShippingIn
    promo_code: str | None = None
    # En prod, ici on recoit un token de paiement (Stripe), jamais le numero de carte.
    payment_token: str | None = None
    # Carte deja enregistree, designee par son identifiant. Le JETON n'est pas
    # transmis par le client et ne lui est jamais rendu : le serveur le retrouve
    # lui-meme a partir de l'identifiant, apres avoir verifie que la carte
    # appartient bien au demandeur. Un jeton qui circule est un jeton qu'on
    # finit par retrouver dans un journal de proxy.
    payment_method_id: int | None = None
    # ACCEPTATION DES CONDITIONS DE VENTE, obligatoire en vente a distance.
    #
    # Verifiee cote SERVEUR et pas seulement par une case a cocher : une
    # validation qui ne vit que dans le navigateur se contourne avec la console,
    # et l'acceptation perdrait toute valeur probante. Le champ est obligatoire
    # sans valeur par defaut - une commande qui l'omet est refusee, ce qui vaut
    # mieux qu'un `False` silencieux.
    cgv_acceptees: bool


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    name: str
    art: str
    unit_price_cents: int
    qty: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    number: str
    email: str
    status: str
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    total_cents: int
    promo_code: str | None
    created_at: datetime
    items: list[OrderItemOut]