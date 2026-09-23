from datetime import datetime
import json
from typing import Annotated

from pydantic import (
    AfterValidator, BaseModel, EmailStr, Field, computed_field, ConfigDict, field_validator,
)

from .antibot import AntiBotFields

# Adresse ramenée en minuscules à l'entrée : un téléphone met une capitale en tête
# (« Marie@... ») et l'adresse ne se retrouvait plus depuis un ordinateur.
Email = Annotated[EmailStr, AfterValidator(str.lower)]

# Date saisie par le sélecteur du navigateur ; vide admis (champ facultatif)
DATE_ISO = r"^(\d{4}-\d{2}-\d{2})?$"

# Langues de l'interface
LANGUE = "^(fr|en|es)$"


def euros(cents: int) -> float:
    return round(cents / 100, 2)


# ---------- Auth ----------
# Les formulaires publics portent un bloc `antibot` (voir app/antibot.py)
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: Email
    # Bornes de forme ; la politique vit dans app/passwords.py
    password: str = Field(min_length=1, max_length=128)
    antibot: AntiBotFields
    civility: str | None = Field(None, pattern="^(M|F|N)$")
    birthdate: str | None = Field(None, pattern=DATE_ISO)
    # Mêmes bornes que les colonnes, et que la modification du profil
    phone: str | None = Field(None, max_length=30)
    addr: str | None = Field(None, max_length=255)
    addr_extra: str | None = Field(None, max_length=255)
    cp: str | None = Field(None, max_length=10)
    city: str | None = Field(None, max_length=120)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(max_length=128)
    antibot: AntiBotFields


class UserOut(BaseModel):
    """Profil renvoyé à son propriétaire. L'administration a `AdminUserOut`."""

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
    email_verified: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class VerifyEmailIn(BaseModel):
    jeton: str = Field(min_length=16, max_length=128)


class ForgotPasswordIn(BaseModel):
    email: Email


class ResetPasswordIn(BaseModel):
    jeton: str = Field(min_length=16, max_length=128)
    # Politique appliquée par passwords.py, comme à l'inscription
    password: str = Field(min_length=1, max_length=200)


# ---------- Compte ----------
class ProfilPatch(BaseModel):
    """Champs modifiables du profil, tous facultatifs.

    Absent : inchangé. Chaîne vide : champ facultatif effacé. E-mail et mot de
    passe ont leurs propres routes.
    """

    name: str | None = Field(None, min_length=2, max_length=120)
    civility: str | None = Field(None, pattern="^(M|F|N)$")
    # Chaîne vide admise : elle efface la date
    birthdate: str | None = Field(None, pattern=DATE_ISO)
    phone: str | None = Field(None, max_length=30)
    addr: str | None = Field(None, max_length=255)
    addr_extra: str | None = Field(None, max_length=255)
    cp: str | None = Field(None, max_length=10)
    city: str | None = Field(None, max_length=120)


class ChangePasswordIn(BaseModel):
    ancien: str = Field(min_length=1, max_length=200)
    nouveau: str = Field(min_length=1, max_length=200)


class ChangeEmailIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=200)


class MotDePasseIn(BaseModel):
    """Reconfirmation d'identité pour une action sensible."""

    password: str = Field(min_length=1, max_length=200)


class SuppressionIn(BaseModel):
    """Effacement du compte : mot de passe et formule recopiée."""

    password: str = Field(min_length=1, max_length=200)
    confirmation: str = Field(min_length=1, max_length=60)


# ---------- Moyens de paiement ----------
class MoyenPaiementIn(BaseModel):
    """Carte vue par le navigateur : ni numéro ni cryptogramme, de quoi l'afficher seulement."""

    reseau: str = Field(pattern="^(visa|mastercard|amex|unknown)$")
    quatre_derniers: str = Field(pattern=r"^\d{4}$")
    exp_mois: int = Field(ge=1, le=12)
    # Une carte émise aujourd'hui peut expirer dans dix ans
    exp_annee: int = Field(ge=2024, le=2099)
    libelle: str | None = Field(None, max_length=40)
    defaut: bool = False


class MoyenPaiementOut(BaseModel):
    # Le jeton du prestataire n'est jamais renvoyé
    model_config = ConfigDict(from_attributes=True)
    id: int
    reseau: str
    quatre_derniers: str
    exp_mois: int
    exp_annee: int
    libelle: str | None = None
    defaut: bool


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
        # Stocké en chaîne JSON
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
    email: Email
    # Le courriel de retour en stock part dans la langue de la page
    lang: str = Field("fr", pattern=LANGUE)
    antibot: AntiBotFields


# ---------- Lettre d'information ----------
class SubscribeIn(BaseModel):
    email: Email
    lang: str = Field("fr", pattern=LANGUE)
    antibot: AntiBotFields


class UnsubscribeIn(BaseModel):
    """Lien de désinscription : numéro d'inscription et signature, sans compte ni mot de passe."""

    id: int = Field(ge=1)
    signature: str = Field(min_length=16, max_length=128)


class SubscribeOut(BaseModel):
    """`code` : offre de bienvenue, seulement si elle est active en base."""

    ok: bool = True
    code: str | None = None


# ---------- Promo ----------
class PromoCheckIn(BaseModel):
    code: str = Field(max_length=40)
    subtotal_cents: int = Field(ge=0)


class PromoOut(BaseModel):
    code: str
    kind: str
    label: str


# ---------- Panier / Checkout ----------
class CartLineIn(BaseModel):
    product_id: int
    qty: int = Field(ge=1, le=99)


# Sans borne, /orders/quote transformait 1,45 Mo de requête en 4,40 Mo de réponse.
# Cent lignes font quatre fois le catalogue.
PANIER_MAX_LIGNES = 100


class QuoteIn(BaseModel):
    items: list[CartLineIn] = Field(max_length=PANIER_MAX_LIGNES)
    promo_code: str | None = Field(None, max_length=40)


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
    """Adresse de livraison, enregistrée sur la commande. Bornes des colonnes."""

    prenom: str = Field(min_length=1, max_length=60)
    nom: str = Field(min_length=1, max_length=99)
    adresse: str = Field(min_length=3, max_length=255)
    cp: str = Field(min_length=2, max_length=10)
    ville: str = Field(min_length=1, max_length=120)

    @field_validator("prenom", "nom", "adresse", "cp", "ville")
    @classmethod
    def _sans_espaces_autour(cls, valeur: str) -> str:
        propre = valeur.strip()
        if not propre:
            raise ValueError("champ vide")
        return propre


class CheckoutIn(BaseModel):
    items: list[CartLineIn] = Field(max_length=PANIER_MAX_LIGNES)
    email: Email
    shipping: ShippingIn
    promo_code: str | None = Field(None, max_length=40)
    # Jeton de paiement du prestataire, jamais un numéro de carte
    payment_token: str | None = Field(None, max_length=64)
    # Carte enregistrée : le serveur retrouve lui-même son jeton
    payment_method_id: int | None = None
    # Obligatoire et sans défaut : vérifié côté serveur
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
    ship_name: str | None = None
    ship_addr: str | None = None
    ship_cp: str | None = None
    ship_city: str | None = None
    created_at: datetime
    items: list[OrderItemOut]
