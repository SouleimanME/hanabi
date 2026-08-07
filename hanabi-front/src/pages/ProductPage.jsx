/** Fiche produit : galerie, achat, avis clients et produits associes. */
import { useState, useEffect } from "react";
import {
  ArrowLeft,
  Heart,
  Bell,
  Check,
  Minus,
  Plus,
  ShoppingBag,
  Truck,
  ShieldCheck,
} from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { Stars } from "../components/ui/Stars.jsx";
import { StarInput } from "../components/ui/StarInput.jsx";
import { StockBadge } from "../components/ui/StockBadge.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { ProductCard } from "../components/catalog/ProductCard.jsx";
import { DeliveryNote } from "../components/ui/DeliveryNote.jsx";
import { Products } from "../lib/api.js";
import { SHIPPING_CENTS, FREE_SHIPPING_CENTS } from "../lib/constants.js";
import { burstFromElement } from "../lib/burst.js";
import { useTilt } from "../hooks/useTilt.js";
import { useReveal } from "../hooks/useReveal.js";
import { useAntiBot } from "../hooks/useAntiBot.js";

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
  // Reutilise useTilt uniquement pour ses variables de position (--mx/--my) :
  // l'inclinaison est desactivee (max: 0), seul le point vise nous interesse.
  const zoom = useTilt({ max: 0 });
  const [reviewsRef, reviewsIn] = useReveal({ threshold: 0.08 });
  const [relatedRef, relatedIn] = useReveal({ threshold: 0.08 });
  // Un defi par formulaire : le serveur lie chaque preuve a son usage.
  const reviewBot = useAntiBot("review");
  const notifyBot = useAntiBot("notify");
  const [qty, setQty] = useState(1);
  const [sel, setSel] = useState(0);
  // Zoom du visuel : etat explicite, pilote au clic. Voir product.css pour la
  // raison du passage du survol au clic.
  const [zoome, setZoome] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [stars, setStars] = useState(5);
  const [text, setText] = useState("");
  const [err, setErr] = useState(null);
  const [notifyEmail, setNotifyEmail] = useState("");
  const [notifyDone, setNotifyDone] = useState(false);
  const [notifyErr, setNotifyErr] = useState(null);
  // Suggestions issues des paniers reels (entrepot decisionnel). Vide tant que
  // la reponse n'est pas la, ou si l'entrepot n'existe pas.
  const [ensemble, setEnsemble] = useState([]);
  const [ensembleRef, ensembleIn] = useReveal({ threshold: 0.08 });
  const imgs = p.images && p.images.length ? p.images : [p.art];
  const max = Math.max(1, p.stock);
  useEffect(() => {
    setSel(0);
    setQty(1);
    setNotifyDone(false);
    setZoome(false);
  }, [p.id]);

  // Changer de visuel dans la galerie sort du zoom : rester grossi sur une
  // autre image, cadree ailleurs, desoriente.
  useEffect(() => setZoome(false), [sel]);

  // Echap sort du zoom. C'est le reflexe attendu de toute vue agrandie, et le
  // seul moyen d'en sortir au clavier sans avoir a retrouver le visuel.
  useEffect(() => {
    if (!zoome) return undefined;
    const surTouche = (e) => {
      if (e.key === "Escape") setZoome(false);
    };
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [zoome]);

  // Mesure d'audience pour le back-office. Volontairement separee de l'effet
  // ci-dessus : celui-ci remet la fiche a zero, celle-la envoie une requete, et
  // les melanger rendrait le rendu dependant du reseau.
  //
  // L'echec est ignore : la fiche doit rester consultable si l'API dort, si le
  // plafond de debit est atteint ou si un bloqueur coupe l'appel. Une statistique
  // manquante est un moindre mal, une page cassee non.
  useEffect(() => {
    Products.view(p.id).catch(() => {});
  }, [p.id]);

  // Suggestions tirees de l'entrepot. L'echec est avale comme la mesure
  // d'audience : ces produits sont un bonus, leur absence ne doit jamais
  // empecher de consulter la fiche.
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

  const submitReview = async () => {
    if (text.trim().length < 3) return;
    let proof;
    try {
      proof = await reviewBot.getProof();
    } catch {
      setErr(t("errAntibot"));
      return;
    }
    const res = await onReview(p.id, stars, text.trim(), proof);
    if (res === "login") {
      onAskLogin();
      return;
    }
    if (res) {
      setErr(res);
      return;
    }
    setText("");
    setStars(5);
    setShowForm(false);
    setErr(null);
  };
  const submitNotify = async () => {
    if (!notifyEmail.includes("@")) {
      setNotifyErr(t("errEmail"));
      return;
    }
    let proof;
    try {
      proof = await notifyBot.getProof();
    } catch {
      setNotifyErr(t("errAntibot"));
      return;
    }
    const res = await onNotify(p.id, notifyEmail.trim(), proof);
    if (res) {
      setNotifyErr(res);
      return;
    }
    setNotifyDone(true);
    setNotifyErr(null);
  };

  return (
    <main className="pp">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={16} /> {t("back")}
      </button>
      <div className="pp-in">
        <div className="gallery">
          {/* Le visuel se rapproche au CLIC, centre sur le point vise
              (--mx/--my ecrites par useTilt) : on inspecte l'objet au lieu de
              le regarder.

              Le zoom etait auparavant lie au survol, si bien qu'on ne pouvait
              revenir a la vue d'ensemble qu'en sortant du visuel - le geste
              naturel, regarder un detail puis reculer, etait impossible. Un
              clic entre, un second sort, Echap aussi. */}
          <div
            className="pp-art zoomable"
            ref={zoom.ref}
            data-zoom={zoome || undefined}
            role="button"
            tabIndex={0}
            aria-pressed={zoome}
            aria-label={zoome ? t("zoomOut") : t("zoomIn")}
            onClick={() => setZoome((z) => !z)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setZoome((z) => !z);
              }
            }}
            onMouseMove={zoom.onMouseMove}
            onMouseEnter={zoom.onMouseEnter}
            onMouseLeave={zoom.onMouseLeave}
          >
            {imgs[sel] && (imgs[sel].startsWith("http") || imgs[sel].startsWith("data:")) ? (
              <img
                src={imgs[sel]}
                alt={p.name}
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
            ) : (
              <ProductArt art={imgs[sel]} />
            )}
            {/* Le favori vit a l'interieur de la zone de zoom : sans arreter la
                propagation, le mettre en favori zoomerait aussi. */}
            <button
              className={"wish pp-wish" + (wished ? " on" : "")}
              onClick={(e) => {
                e.stopPropagation();
                onWish();
              }}
              aria-label={t("ariaFavorites")}
            >
              <Heart size={20} fill={wished ? "currentColor" : "none"} />
            </button>
          </div>
          {imgs.length > 1 && (
            <div className="thumbs">
              {imgs.map((im, i) => (
                <button
                  key={i}
                  className={"thumb" + (i === sel ? " on" : "")}
                  onClick={() => setSel(i)}
                  aria-label={`Vue ${i + 1}`}
                >
                  {im && (im.startsWith("http") || im.startsWith("data:")) ? (
                    <img
                      src={im}
                      alt=""
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  ) : (
                    <ProductArt art={im} small />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="pp-info">
          <span className="mono small muted">
            {p.code} · {t("cat_" + p.category)}
          </span>
          <h1 className="pp-name">{p.name}</h1>
          <div className="pp-rate">
            <Stars value={p.rating_avg} size={16} />
            <span className="muted small">
              {p.rating_count > 0
                ? `${p.rating_avg.toFixed(1)} · ${t("nReviews", { n: p.rating_count })}`
                : t("noReview")}
            </span>
          </div>
          <div className="mono pp-price">{eur(p.price_cents)}</div>
          <div className="pp-stock">
            <StockBadge stock={p.stock} />
          </div>
          <p className="pp-desc">
            {p.blurb}. {t("descSuffix")}
          </p>
          <ul className="pp-specs">
            <li>
              <span>{t("matiere")}</span> {t("matiere_" + p.category)}
            </li>
            <li>
              <span>{t("origine")}</span> {t("origineVal")}
            </li>
            <li>
              <span>{t("entretien")}</span> {t("entretienVal")}
            </li>
          </ul>
          {p.stock === 0 ? (
            <div className="notify">
              <div className="notify-h">
                <Bell size={16} /> {t("notifyTitle")}
              </div>
              {notifyDone ? (
                <div className="notify-ok">
                  <Check size={15} strokeWidth={3} /> {t("notifyOk")}
                </div>
              ) : (
                <>
                  <div className="notify-row">
                    <input
                      type="email"
                      value={notifyEmail}
                      onChange={(e) => {
                        setNotifyEmail(e.target.value);
                        setNotifyErr(null);
                      }}
                      placeholder={t("notifyPh")}
                      onKeyDown={(e) => e.key === "Enter" && submitNotify()}
                      autoComplete="email"
                      inputMode="email"
                      autoCapitalize="none"
                    />
                    <input {...notifyBot.honeypotProps} />
                    <button className="btn-primary" onClick={submitNotify}>
                      {t("notifyBtn")}
                    </button>
                  </div>
                  {notifyErr && <div className="form-err">{notifyErr}</div>}
                </>
              )}
            </div>
          ) : (
            <div className="pp-buy">
              <div className="stepper big">
                <button onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="-">
                  <Minus size={16} />
                </button>
                <span>{qty}</span>
                <button onClick={() => setQty((q) => Math.min(max, q + 1))} aria-label="+">
                  <Plus size={16} />
                </button>
              </div>
              <button
                className="btn-primary grow"
                onClick={(e) => {
                  burstFromElement(e.currentTarget, { count: 34, power: 8 });
                  onAddItem(p.id, qty);
                  onOpenCart();
                }}
              >
                <ShoppingBag size={17} /> {t("add")} · {eur(p.price_cents * qty)}
              </button>
            </div>
          )}
          {/* La date de livraison et le prix du port sont annonces ici, et non
              seulement en caisse : decouvrir des frais a la derniere etape est
              le premier motif d'abandon d'un panier. */}
          <div className="pp-rea">
            <DeliveryNote lang={lang} />
            <span>
              <Truck size={14} />{" "}
              {t("shipFrom", {
                price: eur(SHIPPING_CENTS),
                free: eur.short(FREE_SHIPPING_CENTS),
              })}
            </span>
            <span>
              <ShieldCheck size={14} /> {t("ret30")}
            </span>
          </div>
        </div>
      </div>

      <section className={"reviews reveal" + (reviewsIn ? " in" : "")} ref={reviewsRef}>
        <div className="rev-head">
          <h2>
            {t("reviews")}{" "}
            {p.rating_count > 0 && (
              <span className="mono muted">
                {p.rating_avg.toFixed(1)} / 5 · {p.rating_count}
              </span>
            )}
          </h2>
          <button
            className="btn-ghost"
            onClick={() => (canReview ? setShowForm((s) => !s) : onAskLogin())}
          >
            {canReview ? t("writeReview") : t("loginToRate")}
          </button>
        </div>
        {showForm && canReview && (
          <div className="rev-form">
            <StarInput value={stars} onChange={setStars} />
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={t("reviewPh")}
              rows={3}
            />
            <input {...reviewBot.honeypotProps} />
            {err && (
              <div className="form-err" role="alert">
                {err}
              </div>
            )}
            <button
              className="btn-primary"
              onClick={submitReview}
              disabled={text.trim().length < 3}
            >
              {t("publish")}
            </button>
          </div>
        )}
        {reviews.length === 0 ? (
          <p className="muted rev-empty">{t("firstReview")}</p>
        ) : (
          <div className="rev-list">
            {reviews.map((rv, i) => (
              <div className="rev" key={i}>
                <div className="rev-top">
                  <span className="rev-name">
                    {rv.author_name}
                    {rv.verified && (
                      <span className="rev-mine">
                        <Check size={10} strokeWidth={3} /> {t("verified")}
                      </span>
                    )}
                  </span>
                  <Stars value={rv.rating} size={13} />
                </div>
                <p>{rv.text}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Suggestions issues des paniers reels, et non d'une regle ecrite a la
          main comme « meme categorie ». La table qui les alimente mesure,
          pour chaque paire, a quel point elle depasse le hasard ; seules
          celles qui le depassent vraiment sont proposees. La section
          disparait entierement quand il n'y en a aucune - une rubrique de
          recommandations vide vaut moins que pas de rubrique. */}
      {ensemble.length > 0 && (
        <section
          className={"related ensemble reveal" + (ensembleIn ? " in" : "")}
          ref={ensembleRef}
        >
          <h2>{t("boughtTogether")}</h2>
          <p className="ensemble-note">{t("boughtTogetherNote")}</p>
          <div className="grid">
            {ensemble.map((r) => (
              <ProductCard
                key={r.id}
                p={r}
                onOpen={onOpen}
                onAdd={onAddItem}
                wished={false}
                onWish={() => {}}
                eur={eur}
              />
            ))}
          </div>
        </section>
      )}

      {related.length > 0 && (
        <section className={"related reveal" + (relatedIn ? " in" : "")} ref={relatedRef}>
          <h2>{t("related")}</h2>
          <div className="grid">
            {related.map((r) => (
              <ProductCard
                key={r.id}
                p={r}
                onOpen={onOpen}
                onAdd={onAddItem}
                wished={false}
                onWish={() => {}}
                eur={eur}
              />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

export default ProductPage;
