/** Favoris, conserves dans le navigateur. */
import { ArrowLeft } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { ProductCard } from "../components/catalog/ProductCard.jsx";

export function Wishlist({ items, onOpen, onAdd, onWish, onBack, eur }) {
  const t = useT();
  return (
    <main id="contenu" className="wrap page">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" /> {t("back")}
      </button>
      <div className="page-head">
        <h1 className="page-title">{t("favs")}</h1>
        <span className="muted">{t("itemsN", { n: items.length })}</span>
      </div>
      {items.length === 0 ? (
        <div className="empty">
          <p>{t("favEmpty")}</p>
          <button className="btn btn-primary" onClick={onBack}>
            {t("browse")}
          </button>
        </div>
      ) : (
        <ul className="tray">
          {items.map((p) => (
            <ProductCard
              key={p.id}
              p={p}
              onOpen={onOpen}
              onAdd={onAdd}
              wished
              onWish={onWish}
              eur={eur}
            />
          ))}
        </ul>
      )}
    </main>
  );
}

export default Wishlist;
