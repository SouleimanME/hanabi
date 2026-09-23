/** Paiement. */
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Lock, RotateCcw } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { PromoField } from "../components/cart/PromoField.jsx";
import { ShippingGauge } from "../components/cart/ShippingGauge.jsx";
import { Totals } from "../components/cart/Totals.jsx";
import { DeliveryNote } from "../components/ui/DeliveryNote.jsx";
import { Compte } from "../lib/api.js";
import {
  cardNumberValid,
  cvcLength,
  cvcValid,
  detectBrand,
  digitsOnly,
  expiryValid,
  formatCardNumber,
  formatExpiry,
  jetonDePaiement,
} from "../lib/card.js";

const NOMS_RESEAU = { visa: "Visa", mastercard: "Mastercard", amex: "American Express" };

// Ordre de lecture du formulaire : le focus part sur le premier champ à corriger
const ORDRE = ["email", "prenom", "nom", "adresse", "cp", "ville", "carte", "exp", "cvc", "cgv"];

const ADRESSE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Champ avec son libellé, et son erreur sous le champ, reliée par `aria-describedby`. */
function Champ({ label, erreur, children, id }) {
  return (
    <div className="field" data-invalide={erreur ? "" : undefined}>
      <label htmlFor={id}>{label}</label>
      {children}
      {erreur && (
        <span className="field-error" id={`${id}-err`}>
          {erreur}
        </span>
      )}
    </div>
  );
}

/** Attributs d'accessibilité d'un champ selon son erreur. */
const etatChamp = (id, erreur) => ({
  "aria-invalid": erreur ? true : undefined,
  "aria-describedby": erreur ? `${id}-err` : undefined,
});

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

  // Le profil arrive apres le premier rendu (`/auth/me`)
  const profilApplique = useRef(false);
  useEffect(() => {
    if (!user || profilApplique.current) return;
    profilApplique.current = true;
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

  // `null` tant qu'on ne sait pas : afficher « aucune carte » avant la reponse
  // serait faux une demi-seconde.
  const [cartes, setCartes] = useState(null);
  // `null` : payer avec une nouvelle carte. Sinon, l'identifiant choisi.
  const [carteChoisie, setCarteChoisie] = useState(null);

  useEffect(() => {
    if (!user) return setCartes([]);
    let annule = false;
    Compte.paiements()
      .then((liste) => {
        if (annule) return;
        setCartes(liste);
        const parDefaut = liste.find((m) => m.defaut) || liste[0];
        if (parDefaut) setCarteChoisie(parDefaut.id);
      })
      .catch(() => !annule && setCartes([]));
    return () => {
      annule = true;
    };
  }, [user]);

  // Jamais pre-cochee : une case deja cochee n'est pas un consentement
  const [cgv, setCgv] = useState(false);
  // Erreurs par champ, affichées sous chacun ; `err` garde le refus du serveur
  const [erreurs, setErreurs] = useState({});
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const effacerErreur = (k) => setErreurs((e) => (e[k] ? { ...e, [k]: undefined } : e));
  const set = (k) => (e) => {
    setF((s) => ({ ...s, [k]: e.target.value }));
    effacerErreur(k);
  };

  const brand = detectBrand(f.carte);

  /** Contrôles d'un champ, ou de tous ; rend les messages par champ. */
  const controler = (seul) => {
    const e = {};
    const vise = (k) => !seul || seul === k;
    if (vise("email") && !ADRESSE_EMAIL.test(f.email.trim())) e.email = t("errEmail");
    for (const k of ["prenom", "nom", "adresse", "cp", "ville"]) {
      if (vise(k) && !f[k].trim()) e[k] = t("fieldRequired");
    }
    // Une carte enregistree ne repasse pas par ces controles : ses champs ne
    // sont pas affiches.
    if (carteChoisie === null) {
      if (vise("carte") && !cardNumberValid(f.carte)) e.carte = t("errCard");
      if (vise("exp") && !expiryValid(f.exp)) e.exp = t("errExp");
      if (vise("cvc") && !cvcValid(f.cvc, f.carte)) e.cvc = t("errCvc");
    }
    if (vise("cgv") && !cgv) e.cgv = t("errCgv");
    return e;
  };

  // Un champ de carte se vérifie en le quittant, s'il n'est pas vide
  const verifierEnSortant = (k) => () => {
    if (!f[k]) return;
    setErreurs((e) => ({ ...e, [k]: controler(k)[k] }));
  };

  if (empty) {
    return (
      <main id="contenu" className="wrap page">
        <div className="empty empty-page">
          <h1>{t("cartEmptyTitle")}</h1>
          <p>{t("cartEmpty")}</p>
          <button className="btn btn-primary" onClick={onBack}>
            {t("backShop")}
          </button>
        </div>
      </main>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setErr(null);
    const trouvees = controler();
    setErreurs(trouvees);
    const premier = ORDRE.find((k) => trouvees[k]);
    if (premier) {
      setErr(t("errFormSummary", { n: Object.keys(trouvees).length }));
      document.getElementById(`co-${premier}`)?.focus();
      return;
    }

    setBusy(true);
    try {
      await onPay({
        ...f,
        payment_method_id: carteChoisie,
        // Le numero reste dans le navigateur ; seul un jeton part
        payment_token: carteChoisie === null ? jetonDePaiement(f.carte) : null,
        cgv_acceptees: cgv,
      });
    } catch (error) {
      setErr(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main id="contenu" className="wrap page checkout">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" /> {t("back")}
      </button>
      <div className="checkout-grid">
        <form className="checkout-form" onSubmit={submit} noValidate>
          <h1 className="page-title">{t("payment")}</h1>

          <fieldset className="form-block">
            <legend>{t("contact")}</legend>
            <Champ label={t("email")} id="co-email" erreur={erreurs.email}>
              <input
                id="co-email"
                type="email"
                value={f.email}
                onChange={set("email")}
                autoComplete="email"
                inputMode="email"
                autoCapitalize="none"
                spellCheck="false"
                {...etatChamp("co-email", erreurs.email)}
              />
            </Champ>
          </fieldset>

          <fieldset className="form-block">
            <legend>{t("shipping")}</legend>
            <div className="field-row">
              <Champ label={t("prenom")} id="co-prenom" erreur={erreurs.prenom}>
                <input
                  id="co-prenom"
                  value={f.prenom}
                  onChange={set("prenom")}
                  autoComplete="given-name"
                  maxLength={60}
                  {...etatChamp("co-prenom", erreurs.prenom)}
                />
              </Champ>
              <Champ label={t("nom")} id="co-nom" erreur={erreurs.nom}>
                <input
                  id="co-nom"
                  value={f.nom}
                  onChange={set("nom")}
                  autoComplete="family-name"
                  maxLength={99}
                  {...etatChamp("co-nom", erreurs.nom)}
                />
              </Champ>
            </div>
            <Champ label={t("adresse")} id="co-adresse" erreur={erreurs.adresse}>
              <input
                id="co-adresse"
                value={f.adresse}
                onChange={set("adresse")}
                autoComplete="street-address"
                maxLength={255}
                {...etatChamp("co-adresse", erreurs.adresse)}
              />
            </Champ>
            <div className="field-row">
              <Champ label={t("cp")} id="co-cp" erreur={erreurs.cp}>
                <input
                  id="co-cp"
                  value={f.cp}
                  onChange={set("cp")}
                  inputMode="numeric"
                  autoComplete="postal-code"
                  maxLength={10}
                  {...etatChamp("co-cp", erreurs.cp)}
                />
              </Champ>
              <Champ label={t("ville")} id="co-ville" erreur={erreurs.ville}>
                <input
                  id="co-ville"
                  value={f.ville}
                  onChange={set("ville")}
                  autoComplete="address-level2"
                  maxLength={120}
                  {...etatChamp("co-ville", erreurs.ville)}
                />
              </Champ>
            </div>
          </fieldset>

          <fieldset className="form-block">
            <legend>{t("payment")}</legend>

            {cartes && cartes.length > 0 && (
              <div className="choices" role="radiogroup" aria-label={t("payWith")}>
                {cartes.map((m) => (
                  <label key={m.id} className="choice">
                    <input
                      type="radio"
                      name="carte"
                      checked={carteChoisie === m.id}
                      onChange={() => setCarteChoisie(m.id)}
                    />
                    <span className="choice-main">
                      {NOMS_RESEAU[m.reseau] || t("payCard")}
                      <span className="code"> •••• {m.quatre_derniers}</span>
                    </span>
                    <span className="choice-sub">
                      {String(m.exp_mois).padStart(2, "0")}/{String(m.exp_annee).slice(-2)}
                      {m.libelle ? ` · ${m.libelle}` : ""}
                    </span>
                  </label>
                ))}
                <label className="choice">
                  <input
                    type="radio"
                    name="carte"
                    checked={carteChoisie === null}
                    onChange={() => setCarteChoisie(null)}
                  />
                  <span className="choice-main">{t("payOther")}</span>
                </label>
              </div>
            )}

            {carteChoisie === null && (
              <>
                <Champ label={t("cardNo")} id="co-carte" erreur={erreurs.carte}>
                  <div className="card-input">
                    <input
                      id="co-carte"
                      value={f.carte}
                      onChange={(e) => {
                        setF((s) => ({ ...s, carte: formatCardNumber(e.target.value) }));
                        effacerErreur("carte");
                      }}
                      onBlur={verifierEnSortant("carte")}
                      placeholder="4242 4242 4242 4242"
                      inputMode="numeric"
                      autoComplete="cc-number"
                      {...etatChamp("co-carte", erreurs.carte)}
                    />
                    {brand.label && <span className="card-brand">{brand.label}</span>}
                  </div>
                </Champ>
                <div className="field-row">
                  <Champ label={t("exp")} id="co-exp" erreur={erreurs.exp}>
                    <input
                      id="co-exp"
                      value={f.exp}
                      onChange={(e) => {
                        setF((s) => ({ ...s, exp: formatExpiry(e.target.value) }));
                        effacerErreur("exp");
                      }}
                      onBlur={verifierEnSortant("exp")}
                      placeholder={t("expPh")}
                      inputMode="numeric"
                      autoComplete="cc-exp"
                      {...etatChamp("co-exp", erreurs.exp)}
                    />
                  </Champ>
                  <Champ label={t("cvc")} id="co-cvc" erreur={erreurs.cvc}>
                    <input
                      id="co-cvc"
                      value={f.cvc}
                      onChange={(e) => {
                        setF((s) => ({
                          ...s,
                          cvc: digitsOnly(e.target.value).slice(0, cvcLength(s.carte)),
                        }));
                        effacerErreur("cvc");
                      }}
                      onBlur={verifierEnSortant("cvc")}
                      placeholder={cvcLength(f.carte) === 4 ? "1234" : "123"}
                      inputMode="numeric"
                      autoComplete="cc-csc"
                      {...etatChamp("co-cvc", erreurs.cvc)}
                    />
                  </Champ>
                </div>
              </>
            )}
          </fieldset>

          <div className="field" data-invalide={erreurs.cgv ? "" : undefined}>
            <label className="check">
              <input
                id="co-cgv"
                type="checkbox"
                checked={cgv}
                onChange={(e) => {
                  setCgv(e.target.checked);
                  effacerErreur("cgv");
                }}
                {...etatChamp("co-cgv", erreurs.cgv)}
              />
              <span>
                {t("cgvAccept")}{" "}
                <button type="button" className="link" onClick={() => onOpenLegal?.("cgv")}>
                  {t("cgvLink")}
                </button>
                {t("cgvAcceptEnd")}
              </span>
            </label>
            {erreurs.cgv && (
              <span className="field-error" id="co-cgv-err">
                {erreurs.cgv}
              </span>
            )}
          </div>

          {err && (
            <p className="notice notice-error" role="alert">
              {err}
            </p>
          )}
          <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
            <Lock size={16} aria-hidden="true" />
            {busy ? t("processing") : `${t("pay")} ${eur(disp.total_cents)}`}
          </button>
          <ul className="assurances assurances-stack">
            <li>
              <DeliveryNote lang={lang} />
            </li>
            <li>
              <RotateCcw size={16} aria-hidden="true" /> {t("ret30")}
            </li>
          </ul>
          <p className="demo-note">{t("payDemo")}</p>
        </form>

        <aside className="summary" aria-labelledby="recap-titre">
          <h2 id="recap-titre">{t("recap")}</h2>
          <ul className="lines">
            {lines.map((l) => (
              <li className="line line-compact" key={l.id}>
                <span className="line-art">
                  <ProductArt art={l.product.art} />
                  <span className="line-qty" aria-label={t("qtyN", { n: l.qty })}>
                    {l.qty}
                  </span>
                </span>
                <div className="line-main">
                  <p className="line-name">{l.product.name}</p>
                  <span className="code">{l.product.code}</span>
                </div>
                <span className="price">{eur(l.product.price_cents * l.qty)}</span>
              </li>
            ))}
          </ul>
          <PromoField
            promo={promo}
            promoLabel={promoLabel}
            onApply={onApplyPromo}
            onClear={onClearPromo}
          />
          <ShippingGauge
            subtotalCents={disp.subtotal_cents}
            discountCents={disp.discount_cents}
            eur={eur}
          />
          <Totals disp={disp} eur={eur} />
        </aside>
      </div>
    </main>
  );
}

export default Checkout;
