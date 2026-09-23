"""Rédaction des courriels transactionnels ; l'envoi relève de `mailer.py`.

HTML en tableaux et styles en ligne : les messageries ignorent flex, grid et
souvent `<style>`. La version texte accompagne toujours le HTML.
Couleurs de la charte : vermillon sur washi, texte de laque sur le vermillon.

Les courriels déclenchés depuis une page (lettre, retour en stock) partent dans
la langue de cette page ; ceux du compte et de la commande, en français.
"""
from html import escape

from . import abonnement, models
from .config import settings

VERMILLON = "#d8452b"
VERMILLON_TEXTE = "#ad3116"
LAQUE = "#0a0605"
ENCRE = "#1a0f0b"
DISCRET = "#6b5347"
WASHI = "#efe7d6"
WASHI_CLAIR = "#f7f2e6"

MENTIONS = {
    "fr": "Boutique fictive : aucun paiement n'est encaissé et aucun colis ne sera expédié.",
    "en": "Fictional shop: no payment is taken and no parcel will be shipped.",
    "es": "Tienda ficticia: no se cobra ningún pago ni se envía ningún paquete.",
}
MENTION = MENTIONS["fr"]


def _langue(lang: str | None) -> str:
    return lang if lang in MENTIONS else "fr"


def _euros(cents: int) -> str:
    return f"{cents / 100:.2f} €".replace(".", ",")


def _lien(chemin: str) -> str:
    return f"{settings.PUBLIC_SITE_URL.rstrip('/')}{chemin}"


def _page(titre: str, corps: str, lang: str = "fr") -> str:
    """Enveloppe commune : filet vermillon, colonne centrée, mention de fiction."""
    lang = _langue(lang)
    return f"""<!doctype html>
<html lang="{lang}"><body style="margin:0;padding:24px;background:{WASHI};
  font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:{ENCRE}">
  <table role="presentation" width="100%" style="max-width:560px;margin:0 auto;
    background:{WASHI_CLAIR};border-top:3px solid {VERMILLON};padding:28px">
    <tr><td>
      <p style="font-size:12px;letter-spacing:.16em;font-weight:700;
        color:{VERMILLON_TEXTE};margin:0 0 6px">HANABI</p>
      <h1 style="font-family:Georgia,serif;font-size:24px;margin:0 0 18px">{escape(titre)}</h1>
      {corps}
      <p style="margin:26px 0 0;font-size:12px;color:{DISCRET};line-height:1.6">{MENTIONS[lang]}</p>
    </td></tr>
  </table>
</body></html>"""


def _bouton(url: str, libelle: str) -> str:
    # `href` construit par l'application depuis un jeton alphanumérique ; le libellé est échappé
    return f"""<p style="margin:22px 0">
        <a href="{url}" style="display:inline-block;background:{VERMILLON};
          color:{LAQUE};text-decoration:none;font-weight:700;font-size:14px;
          border-radius:5px;padding:13px 22px">{escape(libelle)}</a></p>
      <p style="margin:0;font-size:12px;color:{DISCRET};line-height:1.6">
        Si le bouton ne fonctionne pas, copie ce lien dans ton navigateur :<br>
        <span style="word-break:break-all">{url}</span></p>"""


def confirmation_adresse(user: models.User, jeton: str) -> tuple[str, str, str]:
    """Lien de confirmation d'adresse, envoyé à l'inscription ou au changement d'e-mail."""
    url = _lien(f"/confirmer-adresse?jeton={jeton}")
    sujet = "Confirme ton adresse e-mail"

    texte = f"""Bienvenue {user.name}.

Ton compte Hanabi est créé. Confirme ton adresse en ouvrant ce lien :

{url}

Ce lien est valable sept jours. Tu peux déjà te connecter et commander : la
confirmation nous assure que nous écrivons à la bonne adresse.

Si tu n'es pas à l'origine de cette inscription, ignore ce message.

Hanabi
"""

    html = _page(
        "Confirme ton adresse",
        f"""<p style="margin:0 0 4px;font-size:15px">Bienvenue {escape(user.name)}.</p>
      <p style="margin:0;color:{DISCRET};font-size:14px;line-height:1.6">
        Ton compte est créé. Tu peux déjà commander : la confirmation nous assure
        que nous écrivons à la bonne adresse.</p>
      {_bouton(url, "Confirmer mon adresse")}
      <p style="margin:16px 0 0;font-size:12px;color:{DISCRET}">
        Lien valable sept jours. Si tu n'es pas à l'origine de cette
        inscription, ignore ce message.</p>""",
    )
    return sujet, texte, html


def reinitialisation_mot_de_passe(user: models.User, jeton: str) -> tuple[str, str, str]:
    """Lien de réinitialisation, formulé pour quelqu'un qui n'a peut-être rien demandé."""
    url = _lien(f"/nouveau-mot-de-passe?jeton={jeton}")
    sujet = "Réinitialiser ton mot de passe"

    texte = f"""Bonjour {user.name},

Quelqu'un a demandé la réinitialisation du mot de passe de ce compte. Si c'est
toi, ouvre ce lien :

{url}

Ce lien expire dans une heure et ne fonctionne qu'une fois.

Si ce n'est pas toi, ignore ce message : ton mot de passe actuel reste valable
et personne n'a eu accès à ton compte.

Hanabi
"""

    html = _page(
        "Réinitialiser ton mot de passe",
        f"""<p style="margin:0 0 4px;font-size:15px">Bonjour {escape(user.name)},</p>
      <p style="margin:0;color:{DISCRET};font-size:14px;line-height:1.6">
        Quelqu'un a demandé la réinitialisation du mot de passe de ce compte.
        Si c'est toi, choisis-en un nouveau.</p>
      {_bouton(url, "Choisir un nouveau mot de passe")}
      <p style="margin:16px 0 0;font-size:12px;color:{DISCRET};line-height:1.6">
        Ce lien expire dans une heure et ne fonctionne qu'une fois.<br>
        Si ce n'est pas toi, ignore ce message : ton mot de passe actuel reste
        valable et personne n'a eu accès à ton compte.</p>""",
    )
    return sujet, texte, html


_LETTRE = {
    "fr": {
        "sujet": "Bienvenue chez Hanabi",
        "sujet_code": "Bienvenue chez Hanabi, ton code {code}",
        "titre": "Merci de ton inscription",
        "code": "Ton code de bienvenue",
        "code_usage": "À saisir dans le panier, sur ta première commande.",
        "sans_code": "L'offre de bienvenue n'est pas disponible pour le moment.",
        # Même promesse que le formulaire du pied de page
        "rythme": "Un e-mail quand une série sort, rien d'autre. Ton adresse ne sera ni revendue ni transmise.",
        "desabo": "Se désinscrire en un clic",
    },
    "en": {
        "sujet": "Welcome to Hanabi",
        "sujet_code": "Welcome to Hanabi, your code {code}",
        "titre": "Thanks for signing up",
        "code": "Your welcome code",
        "code_usage": "Enter it in the cart on your first order.",
        "sans_code": "The welcome offer is not available right now.",
        "rythme": "One e-mail when a new series is out, nothing else. Your address is never sold or shared.",
        "desabo": "Unsubscribe in one click",
    },
    "es": {
        "sujet": "Te damos la bienvenida a Hanabi",
        "sujet_code": "Te damos la bienvenida a Hanabi, tu código {code}",
        "titre": "Gracias por suscribirte",
        "code": "Tu código de bienvenida",
        "code_usage": "Introdúcelo en el carrito en tu primer pedido.",
        "sans_code": "La oferta de bienvenida no está disponible en este momento.",
        "rythme": "Un correo cuando sale una serie, nada más. Tu dirección nunca se vende ni se comparte.",
        "desabo": "Darse de baja con un clic",
    },
}


def bienvenue_newsletter(inscription_id: int, code: str | None, lang: str = "fr") -> tuple[str, str, str]:
    """Confirmation d'inscription à la lettre, avec le code de bienvenue et le lien de désinscription."""
    lang = _langue(lang)
    m = _LETTRE[lang]
    sujet = m["sujet_code"].format(code=code) if code else m["sujet"]
    desabo = abonnement.lien(inscription_id)

    bloc_code = f"{m['code']} : {code}\n{m['code_usage']}\n" if code else f"{m['sans_code']}\n"

    texte = f"""{m['titre']}.

{bloc_code}
{m['rythme']}

{m['desabo']} : {desabo}

Hanabi
"""

    bloc_html = (
        f"""<p style="margin:0 0 6px;color:{DISCRET};font-size:13px">{m['code']}</p>
      <p style="margin:0 0 6px;font-size:26px;font-weight:800;letter-spacing:.08em;
        color:{VERMILLON_TEXTE}">{escape(code)}</p>
      <p style="margin:0;color:{DISCRET};font-size:13px">{m['code_usage']}</p>"""
        if code
        else f"""<p style="margin:0;color:{DISCRET};font-size:14px">{m['sans_code']}</p>"""
    )

    html = _page(
        m["titre"],
        f"""{bloc_html}
      <p style="margin:22px 0 0;color:{DISCRET};font-size:13px;line-height:1.6">
        {m['rythme']}<br>
        <a href="{escape(desabo)}" style="color:{DISCRET}">{m['desabo']}</a></p>""",
        lang,
    )
    return sujet, texte, html


_RETOUR = {
    "fr": {
        "sujet": "{nom} est de retour",
        "intro": "Tu nous avais demandé de te prévenir : {nom} est de nouveau en stock.",
        "note": "Les séries sont courtes : le stock peut repartir vite.",
        "bouton": "Voir l'objet",
        "fin": "Cet e-mail est unique : ta demande d'alerte est maintenant close.",
    },
    "en": {
        "sujet": "{nom} is back",
        "intro": "You asked to be told: {nom} is back in stock.",
        "note": "Series are short, so stock may go quickly.",
        "bouton": "See the object",
        "fin": "This is a one-off e-mail: your alert is now closed.",
    },
    "es": {
        "sujet": "{nom} ha vuelto",
        "intro": "Pediste que te avisáramos: {nom} vuelve a estar disponible.",
        "note": "Las series son cortas: el stock puede agotarse rápido.",
        "bouton": "Ver el objeto",
        "fin": "Este correo es único: tu alerta queda cerrada.",
    },
}


def retour_en_stock(produit_id: int, nom: str, lang: str = "fr") -> tuple[str, str, str]:
    """Alerte de retour en stock, envoyée une seule fois par demande."""
    lang = _langue(lang)
    m = _RETOUR[lang]
    url = _lien(f"/produit/{produit_id}")
    sujet = m["sujet"].format(nom=nom)

    texte = f"""{m['intro'].format(nom=nom)}

{url}

{m['note']}
{m['fin']}

Hanabi
"""

    html = _page(
        sujet,
        f"""<p style="margin:0;color:{DISCRET};font-size:14px;line-height:1.6">
        {escape(m['intro'].format(nom=nom))}</p>
      <p style="margin:22px 0">
        <a href="{url}" style="display:inline-block;background:{VERMILLON};
          color:{LAQUE};text-decoration:none;font-weight:700;font-size:14px;
          border-radius:5px;padding:13px 22px">{m['bouton']}</a></p>
      <p style="margin:0;font-size:12px;color:{DISCRET};line-height:1.6">
        {m['note']}<br>{m['fin']}</p>""",
        lang,
    )
    return sujet, texte, html


def confirmation_commande(commande: models.Order, lignes: list[models.OrderItem]) -> tuple[str, str, str]:
    """(sujet, texte, html) de la confirmation de commande."""
    sujet = f"Commande {commande.number} confirmée"

    articles = "\n".join(
        f"  {ligne.name} × {ligne.qty}   {_euros(ligne.unit_price_cents * ligne.qty)}"
        for ligne in lignes
    )
    adresse = [
        ligne
        for ligne in (
            commande.ship_name,
            commande.ship_addr,
            " ".join(p for p in (commande.ship_cp, commande.ship_city) if p),
        )
        if ligne
    ]
    bloc_adresse = (
        "\nLivraison à :\n" + "\n".join(f"  {morceau}" for morceau in adresse) + "\n"
        if adresse
        else ""
    )

    texte = f"""Merci pour ta commande.

Numéro : {commande.number}

{articles}

Sous-total   {_euros(commande.subtotal_cents)}
Remise       -{_euros(commande.discount_cents)}
Livraison    {_euros(commande.shipping_cents)}
Total        {_euros(commande.total_cents)}
{bloc_adresse}
{MENTION}

Hanabi
"""

    rangs = "".join(
        f"""<tr>
              <td style="padding:8px 0;border-bottom:1px solid #ddd2bc">{escape(ligne.name)}
                <span style="color:{DISCRET}"> × {ligne.qty}</span></td>
              <td style="padding:8px 0;border-bottom:1px solid #ddd2bc;text-align:right">
                {_euros(ligne.unit_price_cents * ligne.qty)}</td>
            </tr>"""
        for ligne in lignes
    )

    html = _page(
        "Commande confirmée",
        f"""<p style="margin:0 0 20px;color:{DISCRET}">Numéro
        <strong style="color:{ENCRE}">{commande.number}</strong></p>

      <table role="presentation" width="100%" style="border-collapse:collapse;font-size:14px">
        {rangs}
        <tr><td style="padding:10px 0">Sous-total</td>
            <td style="padding:10px 0;text-align:right">{_euros(commande.subtotal_cents)}</td></tr>
        <tr><td style="padding:2px 0;color:{VERMILLON_TEXTE}">Remise</td>
            <td style="padding:2px 0;text-align:right;color:{VERMILLON_TEXTE}">
              -{_euros(commande.discount_cents)}</td></tr>
        <tr><td style="padding:2px 0">Livraison</td>
            <td style="padding:2px 0;text-align:right">{_euros(commande.shipping_cents)}</td></tr>
        <tr><td style="padding:12px 0 0;font-weight:700;border-top:2px solid {ENCRE}">Total</td>
            <td style="padding:12px 0 0;text-align:right;font-weight:700;
              border-top:2px solid {ENCRE}">{_euros(commande.total_cents)}</td></tr>
      </table>
      {(
          f'<p style="margin:22px 0 0;font-size:14px;line-height:1.6">'
          f'<span style="color:{DISCRET}">Livraison à</span><br>'
          + "<br>".join(escape(morceau) for morceau in adresse)
          + "</p>"
      ) if adresse else ""}""",
    )

    return sujet, texte, html
