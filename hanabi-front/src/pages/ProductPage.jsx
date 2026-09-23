/** Fiche produit : vues, achat, avis, suggestions. */
import { useState, useEffect } from "react";
import { ArrowLeft, Check, Minus, Plus } from "lucide-react";
import { PictoFavori, PictoPanier } from "../components/brand/Pictos.jsx";
import { useT } from "../i18n/context.jsx";
import { Stars } from "../components/ui/Stars.jsx";
import { StarInput } from "../components/ui/StarInput.jsx";
import { StockBadge } from "../components/ui/StockBadge.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { ProductCard } from "../components/catalog/ProductCard.jsx";
import { DeliveryNote } from "../components/ui/DeliveryNote.jsx";
import { Products } from "../lib/api.js";
import { SHIPPING_CENTS, FREE_SHIPPING_CENTS } from "../lib/constants.js";
import { useAntiBot } from "../hooks/useAntiBot.js";

const AVIS_VISIBLES = 6;

export function ProductPage({
  p,
  reviews,
  onBack,
  onAddItem,
  onOpenCart,
  canReview,
  onReview,
  onAskLogin,
  onNotify,
  wished,
  onWish,
  onOpen,
  related,
  lang,
  eur,
}) {
  const t = useT();
  // Un defi par formulaire : le serveur lie chaque preuve a son usage
  const reviewBot = useAntiBot("review");
  const notifyBot = useAntiBot("notify");
  const [qty, setQty] = useState(1);
  const [vue, setVue] = useState(0);
  const [formOuvert, setFormOuvert] = useState(false);
  const [note, setNote] = useState(5);
  const [texte, setTexte] = useState("");
  const [erreurAvis, setErreurAvis] = useState(null);
  const [notifyEmail, setNotifyEmail] = useState("");
  const [notifyDone, setNotifyDone] = useState(false);
  const [notifyErr, setNotifyErr] = useState(null);
  const [tousLesAvis, setTousLesAvis] = useState(false);
  // Suggestions tirees des paniers reels (entrepot). Vide si l'entrepot
  // n'existe pas : la section ne s'affiche alors pas.
  const [ensemble, setEnsemble] = useState([]);

  const vues = p.images && p.images.length ? p.images : [p.art];
  const max = Math.max(1, p.stock);
  const moisAnnee = new Intl.DateTimeFormat(lang, { month: "long", year: "numeric" });

  useEffect(() => {
    setVue(0);
    setQty(1);
    setNotifyDone(false);
    setTousLesAvis(false);
  }, [p.id]);

  // Mesure d'audience. Un echec (API endormie, bloqueur) ne gene pas la fiche.
  useEffect(() => {
    Products.view(p.id).catch(() => {});
  }, [p.id]);

  useEffect(() => {
    let annule = false;
    setEnsemble([]);
    Products.affinites(p.id, lang)
      .then((liste) => {
        if (!annule) setEnsemble(Array.isArray(liste) ? liste : []);
      })
      .catch(() => {});
    return () => {
      annule = true;
    };
  }, [p.id, lang]);

  const choisirVue = (e) => {
    const pas = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!pas) return;
    e.preventDefault();
    const suivante = (vue + pas + vues.length) % vues.length;
    setVue(suivante);
    e.currentTarget.querySelectorAll('[role="radio"]')[suivante]?.focus();
  };

  const publierAvis = async (e) => {
    e.preventDefault();
    if (texte.trim().length < 3) return;
    let preuve;
    try {
      preuve = await reviewBot.getProof();
    } catch {
      setErreurAvis(t("errAntibot"));
      return;
    }
    const res = await onReview(p.id, note, texte.trim(), preuve);
    if (res === "login") {
      onAskLogin();
      return;
    }
    if (res) {
      setErreurAvis(res);
      return;
    }
    setTexte("");
    setNote(5);
    setFormOuvert(false);
    setErreurAvis(null);
  };

  const demanderAlerte = async (e) => {
    e.preventDefault();
    if (!notifyEmail.includes("@")) {
      setNotifyErr(t("errEmail"));
      return;
    }
    let preuve;
    try {
      preuve = await notifyBot.getProof();
    } catch {
      setNotifyErr(t("errAntibot"));
      return;
    }
    const res = await onNotify(p.id, notifyEmail.trim(), preuve);
    if (res) {
      setNotifyErr(res);
      return;
    }
    setNotifyDone(true);
    setNotifyErr(null);
  };

  return (
    <main id="contenu" className="wrap page product">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" /> {t("back")}
      </button>

      <div className="product-grid">
        <div className="gallery">
          <div
            className="gallery-main"
            role="img"
            aria-label={t("viewOf", { name: p.name, n: vue + 1, total: vues.length })}
          >
            <ProductArt art={vues[vue]} alt={p.name} />
          </div>
          {vues.length > 1 && (
            <div
              className="thumbs"
              role="radiogroup"
              aria-label={t("views")}
              onKeyDown={choisirVue}
            >
              {vues.map((v, i) => (
                <button
                  key={i}
                  type="button"
                  role="radio"
                  aria-checked={i === vue}
                  tabIndex={i === vue ? 0 : -1}
                  aria-label={t("viewN", { n: i + 1, total: vues.length })}
                  onClick={() => setVue(i)}
                >
                  <ProductArt art={v} />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="product-info">
          <p className="product-meta">
            <span className="code">{p.code}</span>
            <span aria-hidden="true">·</span>
            {t("cat_" + p.category)}
          </p>
          <h1 className="product-name">{p.name}</h1>
          <p className="product-rating">
            <Stars value={p.rating_avg} size={16} />
            <span>
              {p.rating_count > 0
                ? `${p.rating_avg.toFixed(1)} · ${t("nReviews", { n: p.rating_count })}`
                : t("noReview")}
            </span>
          </p>
          <div className="product-price">
            <span className="price">{eur(p.price_cents)}</span>
            <StockBadge stock={p.stock} />
          </div>
          <p className="product-desc">
            {p.blurb}. {t("descSuffix")}
          </p>
          {p.stock === 0 ? (
            <form className="notify" onSubmit={demanderAlerte} noValidate>
              <h2>{t("notifyTitle")}</h2>
              {notifyDone ? (
                <p className="notify-ok" role="status">
                  <Check size={16} aria-hidden="true" /> {t("notifyOk")}
                </p>
              ) : (
                <>
                  <div className="notify-row">
                    <label className="sr-only" htmlFor="alerte-email">
                      {t("email")}
                    </label>
                    <input
                      id="alerte-email"
                      type="email"
                      value={notifyEmail}
                      onChange={(e) => {
                        setNotifyEmail(e.target.value);
                        setNotifyErr(null);
                      }}
                      placeholder={t("notifyPh")}
                      autoComplete="email"
                      inputMode="email"
                      autoCapitalize="none"
                      aria-invalid={notifyErr ? true : undefined}
                      aria-describedby={notifyErr ? "alerte-err" : undefined}
                    />
                    <input {...notifyBot.honeypotProps} />
                    <button className="btn btn-primary" type="submit">
                      {t("notifyBtn")}
                    </button>
                  </div>
                  {notifyErr && (
                    <p className="field-error" id="alerte-err" role="alert">
                      {notifyErr}
                    </p>
                  )}
                </>
              )}
            </form>
          ) : (
            <div className="buy">
              <div className="stepper stepper-lg" role="group" aria-label={t("quantity")}>
                <button
                  onClick={() => setQty((q) => Math.max(1, q - 1))}
                  aria-label={t("qtyLess")}
                  disabled={qty <= 1}
                >
                  <Minus size={18} />
                </button>
                <output aria-live="polite">{qty}</output>
                <button
                  onClick={() => setQty((q) => Math.min(max, q + 1))}
                  aria-label={t("qtyMore")}
                  disabled={qty >= max}
                >
                  <Plus size={18} />
                </button>
              </div>
              <button
                className="btn btn-primary buy-add"
                onClick={() => {
                  onAddItem(p.id, qty);
                  onOpenCart();
                }}
              >
                <PictoPanier taille={18} /> {t("add")}
                <span className="price">{eur(p.price_cents * qty)}</span>
              </button>
              <button
                className="icon-btn icon-btn-framed"
                onClick={onWish}
                aria-pressed={wished}
                aria-label={
                  wished ? t("favRemove", { name: p.name }) : t("favAdd", { name: p.name })
                }
              >
                <PictoFavori plein={wished} />
              </button>
            </div>
          )}

          <ul className="reassurance">
            <li>
              <DeliveryNote lang={lang} icone={false} />
            </li>
            <li>
              {t("shipFrom", { price: eur(SHIPPING_CENTS), free: eur.short(FREE_SHIPPING_CENTS) })}
            </li>
            <li>{t("ret30")}</li>
            <li>{t("warranty")}</li>
          </ul>
        </div>
      </div>

      <section className="reviews" aria-labelledby="avis-titre">
        <div className="section-head">
          <h2 id="avis-titre">
            {t("reviews")}
            {p.rating_count > 0 && (
              <span className="section-count">
                {p.rating_avg.toFixed(1)} / 5 · {p.rating_count}
              </span>
            )}
          </h2>
          <button
            className="btn btn-quiet"
            onClick={() => (canReview ? setFormOuvert((o) => !o) : onAskLogin())}
            aria-expanded={canReview ? formOuvert : undefined}
          >
            {canReview ? t("writeReview") : t("loginToRate")}
          </button>
        </div>

        {formOuvert && canReview && (
          <form className="review-form" onSubmit={publierAvis}>
            <StarInput value={note} onChange={setNote} />
            <label className="field">
              <span>{t("reviewLabel")}</span>
              <textarea
                value={texte}
                onChange={(e) => setTexte(e.target.value)}
                placeholder={t("reviewPh")}
                rows={3}
              />
            </label>
            <input {...reviewBot.honeypotProps} />
            {erreurAvis && (
              <p className="field-error" role="alert">
                {erreurAvis}
              </p>
            )}
            <div>
              <button className="btn btn-primary" type="submit" disabled={texte.trim().length < 3}>
                {t("publish")}
              </button>
            </div>
          </form>
        )}

        {reviews.length === 0 ? (
          <p className="muted">{t("firstReview")}</p>
        ) : (
          <ul className="review-list">
            {(tousLesAvis ? reviews : reviews.slice(0, AVIS_VISIBLES)).map((rv) => (
              <li className="review" key={rv.id}>
                <div className="review-head">
                  <span className="review-author">
                    {rv.author_name}
                    {rv.verified && (
                      <span className="review-verified">
                        <Check size={12} strokeWidth={3} aria-hidden="true" /> {t("verified")}
                      </span>
                    )}
                  </span>
                  <Stars value={rv.rating} size={14} />
                </div>
                <p>{rv.text}</p>
                {/* Un avis sans date ne se juge pas : il peut avoir six ans */}
                <time className="review-date" dateTime={rv.created_at}>
                  {moisAnnee.format(new Date(rv.created_at))}
                </time>
              </li>
            ))}
          </ul>
        )}
        {reviews.length > AVIS_VISIBLES && (
          <button
            className="btn btn-quiet reviews-more"
            onClick={() => setTousLesAvis((v) => !v)}
            aria-expanded={tousLesAvis}
          >
            {tousLesAvis ? t("reviewsLess") : t("reviewsAll", { n: reviews.length })}
          </button>
        )}
      </section>

      {ensemble.length > 0 && (
        <section className="suggestions" aria-labelledby="ensemble-titre">
          <div className="section-head">
            <h2 id="ensemble-titre">{t("boughtTogether")}</h2>
          </div>
          <p className="muted">{t("boughtTogetherNote")}</p>
          <ul className="tray tray-compact">
            {ensemble.map((r) => (
              <ProductCard key={r.id} p={r} onOpen={onOpen} onAdd={onAddItem} eur={eur} />
            ))}
          </ul>
        </section>
      )}

      {related.length > 0 && (
        <section className="suggestions" aria-labelledby="associer-titre">
          <div className="section-head">
            <h2 id="associer-titre">{t("related")}</h2>
          </div>
          <ul className="tray tray-compact">
            {related.map((r) => (
              <ProductCard key={r.id} p={r} onOpen={onOpen} onAdd={onAddItem} eur={eur} />
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

export default ProductPage;
