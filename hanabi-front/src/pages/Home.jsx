/** Accueil : l'accroche, la piece du mois, puis le plateau de la selection. */
import { forwardRef } from "react";
import { ArrowRight, Truck, ShieldCheck, ChevronDown } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { CATEGORIES } from "../lib/constants.js";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { ProductCard } from "../components/catalog/ProductCard.jsx";
import { CardSkeleton } from "../components/catalog/CardSkeleton.jsx";
import { Segments } from "../components/catalog/Segments.jsx";

/** Le segment entre crochets de l'accroche est posé sur une plaque de vermillon. */
function surPlaque(titre) {
  return titre.split(/\[(.+?)\]/).map((bout, i) =>
    i % 2 ? (
      <span className="plaque" key={i}>
        {bout}
      </span>
    ) : (
      bout
    ),
  );
}

export const Home = forwardRef(function Home(
  {
    products,
    featured,
    loadErr,
    onOpen,
    onAdd,
    cat,
    onCategoryChange,
    query,
    onClearQuery,
    sort,
    setSort,
    wished,
    onWish,
    recent,
    loading,
    refreshing,
    eur,
  },
  ref,
) {
  const t = useT();

  return (
    <main id="contenu">
      <section className="wrap hero" aria-labelledby="hero-titre">
        <div className="hero-text">
          <p className="eyebrow">
            <span className="jp">限定</span>
            <span aria-hidden="true">·</span>
            {t("limited")}
          </p>
          <h1 id="hero-titre" className="hero-title">
            {surPlaque(t("heroTitle"))}
          </h1>
          <p className="hero-lede">{t("heroSub")}</p>
          <div className="hero-actions">
            <button
              className="btn btn-primary"
              onClick={() => ref.current?.scrollIntoView({ behavior: "smooth" })}
            >
              {t("heroCta")} <ArrowRight size={18} aria-hidden="true" />
            </button>
          </div>
          <ul className="assurances">
            <li>
              <Truck size={16} aria-hidden="true" /> {t("freeShip")}
            </li>
            <li>
              <ShieldCheck size={16} aria-hidden="true" /> {t("warranty")}
            </li>
          </ul>
        </div>

        {featured && (
          <button className="piece" onClick={() => onOpen(featured)}>
            <span className="piece-tag">
              <span className="jp">注目</span> · {t("pieceMonth")}
            </span>
            <span className="piece-art">
              <ProductArt art={featured.art} />
            </span>
            <span className="piece-caption">
              <span>
                <span className="code">{featured.code}</span>
                <span className="piece-name">{featured.name}</span>
              </span>
              <span className="price">{eur(featured.price_cents)}</span>
            </span>
          </button>
        )}
      </section>

      <section className="wrap selection" ref={ref} aria-labelledby="selection-titre">
        <div className="toolbar">
          <div>
            <h2 id="selection-titre">{cat === "Tout" ? t("theDrop") : t("cat_" + cat)}</h2>
            <p className="toolbar-count" aria-live="polite">
              {loading ? " " : t("objectsN", { n: products.length })}
            </p>
          </div>
          <div className="toolbar-controls">
            <Segments categories={CATEGORIES} value={cat} onChange={onCategoryChange} />
            <div className="sort">
              <label htmlFor="tri">{t("sortLabel")}</label>
              <span className="select">
                <select id="tri" value={sort} onChange={(e) => setSort(e.target.value)}>
                  <option value="pop">{t("sortPop")}</option>
                  <option value="new">{t("sortNew")}</option>
                  <option value="asc">{t("sortAsc")}</option>
                  <option value="desc">{t("sortDesc")}</option>
                </select>
                <ChevronDown size={16} aria-hidden="true" />
              </span>
            </div>
          </div>
        </div>

        {loadErr ? (
          <div className="notice notice-error" role="alert">
            <strong>{t("loadFailed")}</strong>
            <span>{loadErr}</span>
          </div>
        ) : loading ? (
          <ul className="tray" aria-busy="true">
            {Array.from({ length: 8 }, (_, i) => (
              <CardSkeleton key={i} />
            ))}
          </ul>
        ) : products.length === 0 ? (
          <div className="empty">
            <h3>{t("noResultTitle")}</h3>
            <p>{query ? t("noResult", { q: query }) : t("noResultCat")}</p>
            <button className="btn btn-quiet" onClick={onClearQuery}>
              {t("showAll")}
            </button>
          </div>
        ) : (
          <ul className="tray" data-refreshing={refreshing || undefined}>
            {products.map((p) => (
              <ProductCard
                key={p.id}
                p={p}
                onOpen={onOpen}
                onAdd={onAdd}
                wished={wished(p.id)}
                onWish={onWish}
                eur={eur}
              />
            ))}
          </ul>
        )}

        {recent.length > 0 && (
          <section className="recent" aria-labelledby="recent-titre">
            <h3 id="recent-titre">{t("recent")}</h3>
            <ul className="recent-list">
              {recent.map((p) => (
                <li key={p.id}>
                  <button className="recent-item" onClick={() => onOpen(p)}>
                    <span className="recent-art">
                      <ProductArt art={p.art} />
                    </span>
                    <span className="recent-name">{p.name}</span>
                    <span className="price">{eur(p.price_cents)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </section>

      <section className="wrap triptyque" aria-labelledby="maison-titre">
        <h2 id="maison-titre">{t("houseTitle")}</h2>
        <ul className="triptyque-list">
          <li>
            <h3>{t("houseMatter")}</h3>
            <p>{t("houseMatterText")}</p>
          </li>
          <li>
            <h3>{t("houseWorkshop")}</h3>
            <p>{t("houseWorkshopText")}</p>
          </li>
          <li>
            <h3>{t("houseUse")}</h3>
            <p>{t("houseUseText")}</p>
          </li>
        </ul>
      </section>
    </main>
  );
});

export default Home;
