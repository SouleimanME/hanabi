"""Redaction des courriels transactionnels.

Separe de `mailer.py`, qui sait remettre un message mais rien de ce qu'il
contient : ici on ecrit, la-bas on expedie. Ce decoupage evite qu'une retouche
de formulation touche au code reseau.

Le HTML reste volontairement rudimentaire - tableaux, styles en ligne, aucune
feuille externe. Ce n'est pas de la negligence : les clients de messagerie
n'appliquent ni `flex`, ni `grid`, ni les balises `<style>` en tete, et une mise
en page moderne s'y effondre. La version texte, elle, n'est pas un repli : c'est
elle que lisent les filtres anti-spam, et un message HTML sans equivalent texte
part au courrier indesirable chez une bonne partie d'entre eux.
"""
from html import escape

from . import models
from .config import settings

COULEUR_ACCENT = "#c33a20"
COULEUR_ENCRE = "#1a0f0b"


def _euros(cents: int) -> str:
    return f"{cents / 100:.2f} €".replace(".", ",")


def _lien(chemin: str) -> str:
    return f"{settings.PUBLIC_SITE_URL.rstrip('/')}{chemin}"


def _page(titre: str, corps: str) -> str:
    """Enveloppe commune : bandeau vermillon, colonne centree, mention legale.

    Les styles sont EN LIGNE et la mise en page repose sur un tableau. Ce n'est
    pas de la negligence : les clients de messagerie n'appliquent ni `flex`, ni
    `grid`, et beaucoup suppriment purement et simplement les balises `<style>`
    en tete du document. Une mise en page moderne s'y effondre.
    """
    return f"""<!doctype html>
<html lang="fr"><body style="margin:0;padding:24px;background:#efe7d6;
  font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:{COULEUR_ENCRE}">
  <table role="presentation" width="100%" style="max-width:560px;margin:0 auto;
    background:#f7f2e6;border-top:3px solid {COULEUR_ACCENT};padding:28px">
    <tr><td>
      <p style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;
        color:{COULEUR_ACCENT};margin:0 0 6px">Hanabi</p>
      <h1 style="font-size:22px;margin:0 0 18px">{escape(titre)}</h1>
      {corps}
      <p style="margin:26px 0 0;font-size:12px;color:#6b5347;line-height:1.6">
        Boutique fictive : aucun paiement n'est encaisse et aucun colis ne sera
        expedie.</p>
    </td></tr>
  </table>
</body></html>"""


def _bouton(url: str, libelle: str) -> str:
    # `href` non echappe a dessein : il est construit par l'application a partir
    # d'un jeton alphanumerique, jamais d'une saisie. Le libelle, lui, l'est.
    return f"""<p style="margin:22px 0">
        <a href="{url}" style="display:inline-block;background:{COULEUR_ACCENT};
          color:#fff;text-decoration:none;font-weight:700;font-size:13px;
          letter-spacing:.08em;text-transform:uppercase;padding:14px 24px">
          {escape(libelle)}</a></p>
      <p style="margin:0;font-size:12px;color:#6b5347;line-height:1.6">
        Si le bouton ne fonctionne pas, copie ce lien dans ton navigateur :<br>
        <span style="word-break:break-all">{url}</span></p>"""


def confirmation_adresse(user: models.User, jeton: str) -> tuple[str, str, str]:
    """Lien de confirmation d'adresse, envoye a l'inscription."""
    url = _lien(f"/confirmer-adresse?jeton={jeton}")
    sujet = "Confirme ton adresse e-mail"

    texte = f"""Bienvenue {user.name}.

Ton compte Hanabi est cree. Confirme ton adresse en ouvrant ce lien :

{url}

Ce lien est valable sept jours. Tu peux deja te connecter et commander sans
attendre : la confirmation nous sert a savoir que nous ecrivons a la bonne
adresse.

Si tu n'es pas a l'origine de cette inscription, ignore ce message.

Hanabi
"""

    html = _page(
        "Confirme ton adresse",
        f"""<p style="margin:0 0 4px;font-size:15px">Bienvenue {escape(user.name)}.</p>
      <p style="margin:0;color:#6b5347;font-size:14px;line-height:1.6">
        Ton compte est cree. Tu peux deja commander : la confirmation nous sert
        a savoir que nous ecrivons a la bonne adresse.</p>
      {_bouton(url, "Confirmer mon adresse")}
      <p style="margin:16px 0 0;font-size:12px;color:#6b5347">
        Lien valable sept jours. Si tu n'es pas a l'origine de cette
        inscription, ignore ce message.</p>""",
    )
    return sujet, texte, html


def reinitialisation_mot_de_passe(user: models.User, jeton: str) -> tuple[str, str, str]:
    """Lien de reinitialisation. Formulation prudente a dessein.

    Le message doit rester juste pour quelqu'un qui n'a rien demande : c'est
    exactement ce que recoit la cible d'une tentative de prise de controle, et
    l'affoler ou lui suggerer que son compte est compromis serait faux.
    """
    url = _lien(f"/nouveau-mot-de-passe?jeton={jeton}")
    sujet = "Reinitialiser ton mot de passe"

    texte = f"""Bonjour {user.name},

Quelqu'un a demande la reinitialisation du mot de passe de ce compte. Si c'est
toi, ouvre ce lien :

{url}

Ce lien expire dans une heure et ne fonctionne qu'une fois.

Si ce n'est pas toi, ignore ce message : ton mot de passe actuel reste valable
et personne n'a eu acces a ton compte.

Hanabi
"""

    html = _page(
        "Reinitialiser ton mot de passe",
        f"""<p style="margin:0 0 4px;font-size:15px">Bonjour {escape(user.name)},</p>
      <p style="margin:0;color:#6b5347;font-size:14px;line-height:1.6">
        Quelqu'un a demande la reinitialisation du mot de passe de ce compte.
        Si c'est toi, choisis-en un nouveau.</p>
      {_bouton(url, "Choisir un nouveau mot de passe")}
      <p style="margin:16px 0 0;font-size:12px;color:#6b5347;line-height:1.6">
        Ce lien expire dans une heure et ne fonctionne qu'une fois.<br>
        Si ce n'est pas toi, ignore ce message : ton mot de passe actuel reste
        valable et personne n'a eu acces a ton compte.</p>""",
    )
    return sujet, texte, html


def bienvenue_newsletter(code: str | None, lang: str = "fr") -> tuple[str, str, str]:
    """Confirmation d'inscription aux annonces, avec le code de bienvenue.

    Le code etait jusqu'ici rendu dans la reponse HTTP et nulle part ailleurs :
    fermer l'onglet le perdait. L'envoyer par courriel le rend retrouvable, ce
    qui est la moindre des choses pour une remise qu'on vient de promettre.
    """
    sujet = "Bienvenue chez Hanabi" + (f" - ton code {code}" if code else "")
    desabo = _lien("/desinscription")

    bloc_code = (
        f"""Ton code de bienvenue : {code}
A saisir dans le panier, sur ta premiere commande.
"""
        if code
        else "L'offre de bienvenue n'est pas disponible pour le moment.\n"
    )

    texte = f"""Merci de ton inscription.

{bloc_code}
Une sortie par semaine, le vendredi. Rien d'autre : ton adresse ne sera ni
revendue ni transmise.

Se desinscrire : {desabo}

Hanabi
"""

    bloc_html = (
        f"""<p style="margin:0 0 6px;color:#6b5347;font-size:13px">
          Ton code de bienvenue</p>
      <p style="margin:0 0 6px;font-size:26px;font-weight:800;letter-spacing:.08em;
        color:{COULEUR_ACCENT}">{escape(code)}</p>
      <p style="margin:0;color:#6b5347;font-size:13px">
        A saisir dans le panier, sur ta premiere commande.</p>"""
        if code
        else """<p style="margin:0;color:#6b5347;font-size:14px">
        L'offre de bienvenue n'est pas disponible pour le moment.</p>"""
    )

    html = _page(
        "Merci de ton inscription",
        f"""{bloc_html}
      <p style="margin:22px 0 0;color:#6b5347;font-size:13px;line-height:1.6">
        Une sortie par semaine, le vendredi. Rien d'autre : ton adresse ne sera
        ni revendue ni transmise.<br>
        <a href="{desabo}" style="color:#6b5347">Se desinscrire</a></p>""",
    )
    return sujet, texte, html


def confirmation_commande(commande: models.Order, lignes: list[models.OrderItem]) -> tuple[str, str, str]:
    """Rend (sujet, texte, html) pour la confirmation d'une commande."""
    sujet = f"Commande {commande.number} confirmee"

    articles = "\n".join(
        f"  - {ligne.name} x{ligne.qty}  {_euros(ligne.unit_price_cents * ligne.qty)}"
        for ligne in lignes
    )
    texte = f"""Merci pour ta commande.

Numero : {commande.number}

{articles}

Sous-total   {_euros(commande.subtotal_cents)}
Remise       -{_euros(commande.discount_cents)}
Livraison    {_euros(commande.shipping_cents)}
Total        {_euros(commande.total_cents)}

Cette boutique est fictive : aucun paiement n'est encaisse et aucun colis ne
sera expedie.

Hanabi
"""

    rangs = "".join(
        f"""<tr>
              <td style="padding:8px 0;border-bottom:1px solid #ddd2bc">{ligne.name}
                <span style="color:#6b5347"> x{ligne.qty}</span></td>
              <td style="padding:8px 0;border-bottom:1px solid #ddd2bc;text-align:right">
                {_euros(ligne.unit_price_cents * ligne.qty)}</td>
            </tr>"""
        for ligne in lignes
    )

    html = f"""<!doctype html>
<html lang="fr"><body style="margin:0;padding:24px;background:#efe7d6;
  font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:{COULEUR_ENCRE}">
  <table role="presentation" width="100%" style="max-width:560px;margin:0 auto;
    background:#f7f2e6;border-top:3px solid {COULEUR_ACCENT};padding:28px">
    <tr><td>
      <p style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;
        color:{COULEUR_ACCENT};margin:0 0 6px">Hanabi</p>
      <h1 style="font-size:22px;margin:0 0 18px">Commande confirmee</h1>
      <p style="margin:0 0 20px;color:#6b5347">Numero
        <strong style="color:{COULEUR_ENCRE}">{commande.number}</strong></p>

      <table role="presentation" width="100%" style="border-collapse:collapse;font-size:14px">
        {rangs}
        <tr><td style="padding:10px 0">Sous-total</td>
            <td style="padding:10px 0;text-align:right">{_euros(commande.subtotal_cents)}</td></tr>
        <tr><td style="padding:2px 0;color:{COULEUR_ACCENT}">Remise</td>
            <td style="padding:2px 0;text-align:right;color:{COULEUR_ACCENT}">
              -{_euros(commande.discount_cents)}</td></tr>
        <tr><td style="padding:2px 0">Livraison</td>
            <td style="padding:2px 0;text-align:right">{_euros(commande.shipping_cents)}</td></tr>
        <tr><td style="padding:12px 0 0;font-weight:700;border-top:2px solid {COULEUR_ENCRE}">Total</td>
            <td style="padding:12px 0 0;text-align:right;font-weight:700;
              border-top:2px solid {COULEUR_ENCRE}">{_euros(commande.total_cents)}</td></tr>
      </table>

      <p style="margin:26px 0 0;font-size:12px;color:#6b5347;line-height:1.6">
        Cette boutique est fictive : aucun paiement n'est encaisse et aucun colis
        ne sera expedie.</p>
    </td></tr>
  </table>
</body></html>"""

    return sujet, texte, html
