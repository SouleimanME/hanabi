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


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


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