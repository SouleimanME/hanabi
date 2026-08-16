/** Tunnel de paiement.
 *
 * Aucune donnee de carte ne quitte le navigateur : le formulaire ne transmet
 * que l'e-mail et l'adresse de livraison, et rien n'est encaisse. La mention
 * sous le bouton le dit au visiteur, pour que personne ne saisisse une vraie
 * carte sur un site qui n'a pas de prestataire de paiement.
 *
 * Le branchement reel consisterait a remplacer ces champs par le composant du
 * prestataire (Stripe Elements et equivalents) : le numero ne transiterait alors
 * ni par ce code ni par le serveur, qui ne recevrait qu'un jeton. Le schema
 * `CheckoutIn` du backend prevoit deja ce `payment_token`.
 */
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Lock, ShieldCheck, RotateCcw } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { PromoField } from "../components/cart/PromoField.jsx";
import { ShippingGauge } from "../components/cart/ShippingGauge.jsx";
import { DeliveryNote } from "../components/ui/DeliveryNote.jsx";
import { Compte } from "../lib/api.js";

/* Noms d'affichage des reseaux. Une table plutot qu'un `text-transform:
   capitalize` en CSS : celui-ci capitalisait aussi « Utiliser une autre
   carte », et n'aurait de toute facon jamais produit « American Express »
   a partir de « amex ». */
const NOMS_RESEAU = {
  visa: "Visa",
  mastercard: "Mastercard",
  amex: "American Express",
};
import {
  cardNumberValid,
  cvcLength,
  cvcValid,
  detectBrand,
  digitsOnly,
  expiryValid,
  formatCardNumber,
  formatExpiry,
} from "../lib/card.js";

export function Checkout({
  lines,
  disp,
  promo,
  promoLabel,
  onApplyPromo,
  onClearPromo,
  user,
  onBack,
  onPay,
  onOpenLegal,
  empty,
  lang,
  eur,
}) {
  const t = useT();
  // PRE-REMPLI DEPUIS LE PROFIL. Un client connecte a deja donne son adresse a
  // l'inscription : la lui redemander a chaque commande est la friction la plus
  // couteuse d'un tunnel d'achat, et elle etait ici gratuite - les champs
  // existaient en base et personne ne les lisait.
  //
  // Le nom est coupe au premier espace, faute de mieux : le profil porte un nom
  // complet, le formulaire deux champs. Le decoupage est faillible - « Marie
  // Claire Dupont » donne « Marie » et « Claire Dupont » - mais il propose au
  // lieu d'imposer, et tout reste modifiable.
  const [f, setF] = useState({
    email: "",
    prenom: "",
    nom: "",
    adresse: "",
    cp: "",
    ville: "",
    carte: "",
    exp: "",
    cvc: "",
  });

  // Le profil arrive APRES le premier rendu.
  //
  // `useAuth` restaure la session par un appel a `/auth/me` : au montage de cet
  // ecran, `user` vaut encore `null`. Un pre-remplissage pose dans l'etat
  // initial ne voyait donc rien, et les champs restaient vides des qu'on
  // arrivait directement sur l'adresse `/commande` - par un lien, un signet ou
  // un simple rechargement. C'est ce qu'a montre la verification en conditions
  // reelles, alors que le code paraissait juste.
  //
  // On remplit donc a l'arrivee du profil, et SEULEMENT les champs encore
  // vides : quelqu'un qui a commence a saisir pendant le chargement ne doit pas
  // voir sa frappe remplacee.
  const profilApplique = useRef(false);
  useEffect(() => {
    if (!user || profilApplique.current) return;
    profilApplique.current = true;

    // Le profil porte un nom complet, le formulaire deux champs. Le decoupage
    // au premier espace est faillible - « Marie Claire Dupont » donne « Marie »
    // puis « Claire Dupont » - mais il PROPOSE au lieu d'imposer, et tout reste
    // modifiable.
    const [prenom = "", ...reste] = (user.name || "").trim().split(/\s+/);
    const duProfil = {
      email: user.email || "",
      prenom,
      nom: reste.join(" "),
      adresse: user.addr || "",
      cp: user.cp || "",
      ville: user.city || "",
    };
    setF((s) => {
      const suite = { ...s };
      for (const [champ, valeur] of Object.entries(duProfil)) {
        if (!s[champ]) suite[champ] = valeur;
      }
      return suite;
    });
  }, [user]);

  // Cartes enregistrees. `null` tant qu'on ne sait pas, tableau vide ensuite :
  // afficher « aucune carte » avant d'avoir demande serait un mensonge d'une
  // demi-seconde, mais un mensonge quand meme.
  const [cartes, setCartes] = useState(null);
  // `null` = payer avec une nouvelle carte. Sinon, identifiant de la carte
  // choisie.
  const [carteChoisie, setCarteChoisie] = useState(null);

  useEffect(() => {
    if (!user) return setCartes([]);
    let annule = false;
    Compte.paiements()
      .then((liste) => {
        if (annule) return;
        setCartes(liste);
        // La carte par defaut est preselectionnee : c'est la raison d'etre du
        // drapeau, et laisser le choix vide obligerait a un clic pour rien.
        const parDefaut = liste.find((m) => m.defaut) || liste[0];
        if (parDefaut) setCarteChoisie(parDefaut.id);
      })
      .catch(() => !annule && setCartes([]));
    return () => {
      annule = true;
    };
  }, [user]);
  // ACCEPTATION DES CONDITIONS DE VENTE.
  //
  // Jamais pre-cochee : une case deja cochee n'est pas un consentement, c'est
  // une case deja cochee. Le RGPD comme le droit de la consommation demandent un
  // acte positif.
  const [cgv, setCgv] = useState(false);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  // Les erreurs de carte n'apparaissent qu'apres une premiere tentative ou une
  // sortie de champ : signaler « numero invalide » au deuxieme chiffre saisi
  // est decourageant.
  const [touched, setTouched] = useState(false);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));

  const brand = detectBrand(f.carte);
  const cardOk = cardNumberValid(f.carte);
  const expOk = expiryValid(f.exp);
  const cvcOk = cvcValid(f.cvc, f.carte);
  if (empty)
    return (
      <main className="co">
        <div className="co-empty">
          <h1>{t("cartEmptyTitle")}</h1>
          <button className="btn-primary" onClick={onBack}>
            {t("backShop")}
          </button>
        </div>
      </main>
    );
  const submit = async () => {
    setErr(null);
    setTouched(true);
    if (!f.email.includes("@")) return setErr(t("errEmail"));
    for (const [k, label] of [
      ["prenom", t("prenom")],
      ["nom", t("nom")],
      ["adresse", t("adresse")],
      ["cp", t("cp")],
      ["ville", t("ville")],
    ])
      if (!f[k].trim()) return setErr(t("required", { f: label }));
    // Une carte enregistree ne repasse pas par ces controles : ses champs ne
    // sont pas affiches, et les valider reviendrait a exiger une saisie qu'on
    // vient precisement d'eviter.
    if (carteChoisie === null) {
      // Le numero est verifie par la cle de Luhn, pas seulement par sa longueur :
      // un chiffre transpose etait accepte et n'echouait qu'au paiement.
      if (!cardNumberValid(f.carte)) return setErr(t("errCard"));
      if (!expiryValid(f.exp)) return setErr(t("errExp"));
      if (!cvcValid(f.cvc, f.carte)) return setErr(t("errCvc"));
    }
    // Le serveur refuse aussi, mais le dire ici evite un aller-retour pour une
    // erreur que l'ecran connait deja.
    if (!cgv) return setErr(t("errCgv"));

    setBusy(true);
    try {
      await onPay({ ...f, payment_method_id: carteChoisie, cgv_acceptees: cgv });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="co">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={16} /> {t("back")}
      </button>
      <div className="co-in">
        <div className="co-form">
          <h1 className="co-h">{t("payment")}</h1>
          <fieldset className="co-block">
            <legend>{t("contact")}</legend>
            <label className="field">
              <span>{t("email")}</span>
              <input
                type="email"
                value={f.email}
                onChange={set("email")}
                placeholder="toi@exemple.fr"
                autoComplete="email"
                inputMode="email"
                autoCapitalize="none"
              />
            </label>
          </fieldset>
          <fieldset className="co-block">
            <legend>{t("shipping")}</legend>
            <div className="row2">
              <label className="field">
                <span>{t("prenom")}</span>
                <input value={f.prenom} onChange={set("prenom")} autoComplete="given-name" />
              </label>
              <label className="field">
                <span>{t("nom")}</span>
                <input value={f.nom} onChange={set("nom")} autoComplete="family-name" />
              </label>
            </div>
            <label className="field">
              <span>{t("adresse")}</span>
              <input value={f.adresse} onChange={set("adresse")} autoComplete="street-address" />
            </label>
            <div className="row2">
              <label className="field">
                <span>{t("cp")}</span>
                <input
                  value={f.cp}
                  onChange={set("cp")}
                  inputMode="numeric"
                  autoComplete="postal-code"
                />
              </label>
              <label className="field">
                <span>{t("ville")}</span>
                <input value={f.ville} onChange={set("ville")} autoComplete="address-level2" />
              </label>
            </div>
          </fieldset>
          <fieldset className="co-block">
            <legend>
              <Lock size={13} /> {t("payment")}
            </legend>

            {/* Cartes enregistrees. Rien ne s'affiche pour un invite ni pour un
                compte qui n'en a aucune : proposer un choix vide ajoute une
                question la ou il n'y en a pas. */}
            {cartes && cartes.length > 0 && (
              <div className="co-cartes" role="radiogroup" aria-label={t("payment")}>
                {cartes.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    role="radio"
                    aria-checked={carteChoisie === m.id}
                    className={"co-carte" + (carteChoisie === m.id ? " on" : "")}
                    onClick={() => setCarteChoisie(m.id)}
                  >
                    <span className="co-carte-nom">
                      {NOMS_RESEAU[m.reseau] || t("payCard")}
                      <span className="mono"> •••• {m.quatre_derniers}</span>
                    </span>
                    <span className="muted small">
                      {String(m.exp_mois).padStart(2, "0")}/{String(m.exp_annee).slice(-2)}
                      {m.libelle ? ` · ${m.libelle}` : ""}
                    </span>
                  </button>
                ))}
                <button
                  type="button"
                  role="radio"
                  aria-checked={carteChoisie === null}
                  className={"co-carte" + (carteChoisie === null ? " on" : "")}
                  onClick={() => setCarteChoisie(null)}
                >
                  <span className="co-carte-nom">{t("payOther")}</span>
                </button>
              </div>
            )}

            {/* Les champs de saisie disparaissent quand une carte enregistree
                est choisie : les laisser visibles mais inertes ferait croire a
                une saisie obligatoire. */}
            {carteChoisie !== null ? null : (
              <>
                <label className="field">
                  <span>{t("cardNo")}</span>
                  <div className="card-input">
                    <input
                      value={f.carte}
                      onChange={(e) =>
                        setF((s) => ({ ...s, carte: formatCardNumber(e.target.value) }))
                      }
                      onBlur={() => setTouched(true)}
                      placeholder="4242 4242 4242 4242"
                      inputMode="numeric"
                      autoComplete="cc-number"
                      aria-invalid={touched && f.carte && !cardOk ? true : undefined}
                    />
                    {/* Reseau reconnu : confirme que la saisie est bien lue. */}
                    {brand.label && <span className="card-brand">{brand.label}</span>}
                  </div>
                  {touched && f.carte && !cardOk && (
                    <span className="field-err">{t("errCard")}</span>
                  )}
                </label>
                <div className="row2">
                  <label className="field">
                    <span>{t("exp")}</span>
                    <input
                      value={f.exp}
                      onChange={(e) => setF((s) => ({ ...s, exp: formatExpiry(e.target.value) }))}
                      onBlur={() => setTouched(true)}
                      placeholder="MM/AA"
                      inputMode="numeric"
                      autoComplete="cc-exp"
                      aria-invalid={touched && f.exp.length >= 5 && !expOk ? true : undefined}
                    />
                    {touched && f.exp.length >= 5 && !expOk && (
                      <span className="field-err">{t("errExp")}</span>
                    )}
                  </label>
                  <label className="field">
                    <span>{t("cvc")}</span>
                    <input
                      value={f.cvc}
                      onChange={(e) =>
                        setF((s) => ({
                          ...s,
                          // American Express utilise 4 chiffres, les autres 3.
                          cvc: digitsOnly(e.target.value).slice(0, cvcLength(s.carte)),
                        }))
                      }
                      onBlur={() => setTouched(true)}
                      placeholder={cvcLength(f.carte) === 4 ? "1234" : "123"}
                      inputMode="numeric"
                      autoComplete="cc-csc"
                      aria-invalid={touched && f.cvc && !cvcOk ? true : undefined}
                    />
                    {touched && f.cvc && !cvcOk && <span className="field-err">{t("errCvc")}</span>}
                  </label>
                </div>
              </>
            )}
          </fieldset>
          {/* Juste au-dessus du bouton : c'est le dernier endroit ou le regard
              passe avant de payer. Plus haut, elle serait oubliee ; en dessous,
              elle arriverait apres la decision. */}
          <label className="co-cgv">
            <input
              type="checkbox"
              checked={cgv}
              onChange={(e) => setCgv(e.target.checked)}
              aria-invalid={touched && !cgv ? true : undefined}
            />
            <span>
              {t("cgvAccept")}{" "}
              <button type="button" className="co-cgv-lien" onClick={() => onOpenLegal?.("cgv")}>
                {t("cgvLink")}
              </button>
              {t("cgvAcceptEnd")}
            </span>
          </label>

          {err && <div className="form-err">{err}</div>}
          <button className="btn-primary full" onClick={submit} disabled={busy}>
            <Lock size={15} /> {busy ? t("processing") : `${t("pay")} ${eur(disp.total_cents)}`}
          </button>
          {/* Reassurance juste sous le bouton : c'est l'instant ou l'acheteur
              hesite le plus, et ou rappeler delai, retour et securite compte. */}
          <div className="pp-rea co-rea">
            <DeliveryNote lang={lang} />
            <span>
              <RotateCcw size={14} /> {t("ret30")}
            </span>
            <span>
              <Lock size={14} /> {t("securePay")}
            </span>
          </div>
          <p className="modal-note">
            <ShieldCheck size={12} /> {t("payDemo")}
          </p>
        </div>
        <aside className="co-sum">
          <h3>{t("recap")}</h3>
          <div className="co-lines">
            {lines.map((l) => (
              <div className="co-line" key={l.id}>
                <div className="co-thumb">
                  <ProductArt art={l.product.art} small />
                  <span className="co-qty">{l.qty}</span>
                </div>
                <div className="co-line-mid">
                  <span className="cart-l-name">{l.product.name}</span>
                  <span className="mono small muted">{l.product.code}</span>
                </div>
                <span className="mono price">{eur(l.product.price_cents * l.qty)}</span>
              </div>
            ))}
          </div>
          <PromoField
            promo={promo}
            promoLabel={promoLabel}
            onApply={onApplyPromo}
            onClear={onClearPromo}
          />
          <div className="sum-row">
            <span>{t("subtotal")}</span>
            <span className="mono">{eur(disp.subtotal_cents)}</span>
          </div>
          {disp.discount_cents > 0 && (
            <div className="sum-row disc">
              <span>{t("discount")}</span>
              <span className="mono">−{eur(disp.discount_cents)}</span>
            </div>
          )}
          <div className="sum-row">
            <span>{t("shipping")}</span>
            <span className="mono">
              {disp.shipping_cents === 0 ? t("free") : eur(disp.shipping_cents)}
            </span>
          </div>
          <ShippingGauge
            subtotalCents={disp.subtotal_cents}
            discountCents={disp.discount_cents}
            eur={eur}
          />
          <div className="sum-row total">
            <span>{t("total")}</span>
            <span className="mono">{eur(disp.total_cents)}</span>
          </div>
        </aside>
      </div>
    </main>
  );
}

export default Checkout;
