/** Page d'accueil : banniere, carrousel, grille de la selection, vus recemment. */
import { forwardRef, useMemo } from "react";
import { ArrowRight, Truck, ShieldCheck, Clock, AlertCircle } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { Dropdown } from "../components/ui/Dropdown.jsx";
import { Stars } from "../components/ui/Stars.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { ProductCard } from "../components/catalog/ProductCard.jsx";
import { Carousel } from "../components/catalog/Carousel.jsx";
import { CardSkeleton } from "../components/catalog/CardSkeleton.jsx";
import { Fireworks } from "../components/brand/Fireworks.jsx";
import { Kamon } from "../components/brand/Ornaments.jsx";
import { useTilt } from "../hooks/useTilt.js";
import { useReveal } from "../hooks/useReveal.js";
import { usePauseHorsEcran } from "../hooks/usePauseHorsEcran.js";

/** Met le dernier mot du titre en valeur (degrade anime via <em>). */
function renderTitle(title) {
  const words = title.trim().split(" ");
  if (words.length < 2) return title;
  const last = words.pop();
  return (
    <>
      {words.join(" ")} <em>{last}</em>
    </>
  );
}

export const Home = forwardRef(function Home(
  {
    products,
    featuredList,
    loadErr,
    onOpen,
    onAdd,
    cat,
    query,
    sort,
    setSort,
    wished,
    onWish,
    recent,
    featured,
    loading,
    refreshing,
    theme,
    eur,
  },
  ref,
) {
  const t = useT();
  const heroTilt = useTilt({ max: 7 });
  const [carouRef, carouIn] = useReveal({ threshold: 0.1 });
  const [recentRef, recentIn] = useReveal({ threshold: 0.1 });
  // Carrousel : produits "featured" choisis dans l'admin en priorité,
  // sinon repli automatique sur les nouveautés puis les premiers produits.
  const spotlight = useMemo(() => {
    if (featuredList && featuredList.length > 0) return featuredList;
    const news = products.filter((p) => p.is_new);
    const rest = products.filter((p) => !p.is_new);
    return [...news, ...rest].slice(0, 5);
  }, [featuredList, products]);

  const hero = usePauseHorsEcran();

  return (
    <main>
      <section className="hero" ref={hero}>
        <div className="hero-maru" aria-hidden="true" />
        <div className="hero-glow" aria-hidden="true" />
        <Fireworks theme={theme} />
        <div className="hero-l">
          <span className="eyebrow">{t("limited")}</span>
          <h1 className="hero-h">{renderTitle(t("heroTitle"))}</h1>
          <p className="hero-p">{t("heroSub")}</p>
          <button
            className="btn-primary"
            onClick={() => ref.current?.scrollIntoView({ behavior: "smooth" })}
          >
            {t("heroCta")} <ArrowRight size={17} />
          </button>
          <div className="hero-meta">
            <span>
              <Truck size={15} /> {t("freeShip")}
            </span>
            <span>
              <ShieldCheck size={15} /> {t("warranty")}
            </span>
          </div>
        </div>
        {featured && (
          <button
            className="hero-card"
            onClick={() => onOpen(featured)}
            ref={heroTilt.ref}
            onMouseEnter={heroTilt.onMouseEnter}
            onMouseMove={heroTilt.onMouseMove}
            onMouseLeave={heroTilt.onMouseLeave}
          >
            <div className="hero-art">
              <ProductArt art={featured.art} />
              <span className="card-sheen" aria-hidden="true" />
            </div>
            <div className="hero-card-ft">
              <div>
                <span className="mono small">{featured.code}</span>
                <div className="hero-card-name">{featured.name}</div>
                <Stars value={featured.rating_avg} count={featured.rating_count} size={13} />
              </div>
              <span className="mono price">{eur(featured.price_cents)}</span>
            </div>
            <span className="hero-tag">{t("pieceMonth")}</span>
          </button>
        )}
        <span className="vlabel" aria-hidden="true">
          花火・限定
        </span>
      </section>

      {cat === "Tout" && !query && spotlight.length > 0 && (
        <div className={"carou-wrap reveal" + (carouIn ? " in" : "")} ref={carouRef}>
          <h2 className="carou-title">{t("spotlight")}</h2>
          <Carousel items={spotlight} onOpen={onOpen} onAdd={onAdd} eur={eur} />
        </div>
      )}

      <section className="grid-sec" ref={ref}>
        {/* Blason en filigrane : donne du fond a la section sans distraire. */}
        <Kamon size={380} />
        <div className="grid-head">
          <h2>{cat === "Tout" ? t("theDrop") : t("cat_" + cat)}</h2>
          <div className="grid-tools">
            {/* Sans `mono` : c'est une legende, pas une donnee a aligner. */}
            <span className="small muted">
              {products.length} {t("refs")}
            </span>
            <Dropdown
              value={sort}
              onChange={setSort}
              options={[
                { value: "pop", label: t("sortPop") },
                { value: "new", label: t("sortNew") },
                { value: "asc", label: t("sortAsc") },
                { value: "desc", label: t("sortDesc") },
              ]}
            />
          </div>
        </div>
        {loadErr ? (
          <div className="api-down">
            <AlertCircle size={22} />
            <div>
              <strong>{loadErr}</strong>
            </div>
          </div>
        ) : loading ? (
          <div className="grid">
            {Array.from({ length: 6 }, (_, i) => (
              <CardSkeleton key={i} index={i} />
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="empty-grid">{t("noResult", { q: query })}</div>
        ) : (
          <div className={"grid" + (refreshing ? " is-refreshing" : "")}>
            {products.map((p, i) => (
              <ProductCard
                key={p.id}
                p={p}
                index={i}
                onOpen={onOpen}
                onAdd={onAdd}
                wished={wished(p.id)}
                onWish={onWish}
                eur={eur}
              />
            ))}
          </div>
        )}
        {recent.length > 0 && (
          <div className={"recent reveal" + (recentIn ? " in" : "")} ref={recentRef}>
            <h3 className="recent-h">
              <Clock size={16} /> {t("recent")}
            </h3>
            <div className="recent-row">
              {recent.map((p) => (
                <button key={p.id} className="recent-card" onClick={() => onOpen(p)}>
                  <div className="recent-art">
                    <ProductArt art={p.art} small />
                  </div>
                  <div className="recent-info">
                    <span className="recent-name">{p.name}</span>
                    <span className="mono price small">{eur(p.price_cents)}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </section>
    </main>
  );
});

export default Home;
