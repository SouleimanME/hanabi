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
import { useState } from "react";
import { ArrowLeft, Lock, ShieldCheck, RotateCcw } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { PromoField } from "../components/cart/PromoField.jsx";
import { ShippingGauge } from "../components/cart/ShippingGauge.jsx";
import { DeliveryNote } from "../components/ui/DeliveryNote.jsx";
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
  empty,
  lang,
  eur,
}) {
  const t = useT();
  const [f, setF] = useState({
    email: user?.email || "",
    prenom: "",
    nom: "",
    adresse: "",
    cp: "",
    ville: "",
    carte: "",
    exp: "",
    cvc: "",
  });
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
    // Le numero est verifie par la cle de Luhn, pas seulement par sa longueur :
    // un chiffre transpose etait accepte et n'echouait qu'au paiement.
    if (!cardNumberValid(f.carte)) return setErr(t("errCard"));
    if (!expiryValid(f.exp)) return setErr(t("errExp"));
    if (!cvcValid(f.cvc, f.carte)) return setErr(t("errCvc"));
    setBusy(true);
    try {
      await onPay(f);
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
            <label className="field">
              <span>{t("cardNo")}</span>
              <div className="card-input">
                <input
                  value={f.carte}
                  onChange={(e) => setF((s) => ({ ...s, carte: formatCardNumber(e.target.value) }))}
                  onBlur={() => setTouched(true)}
                  placeholder="4242 4242 4242 4242"
                  inputMode="numeric"
                  autoComplete="cc-number"
                  aria-invalid={touched && f.carte && !cardOk ? true : undefined}
                />
                {/* Reseau reconnu : confirme que la saisie est bien lue. */}
                {brand.label && <span className="card-brand">{brand.label}</span>}
              </div>
              {touched && f.carte && !cardOk && <span className="field-err">{t("errCard")}</span>}
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
          </fieldset>
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
