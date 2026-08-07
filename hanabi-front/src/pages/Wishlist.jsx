/** Favoris de l'utilisateur, conserves en localStorage. */
import { ArrowLeft, Heart } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { ProductCard } from "../components/catalog/ProductCard.jsx";

export function Wishlist({ items, onOpen, onAdd, onWish, onBack, eur }) {
  const t = useT();
  return (
    <main className="pp">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={16} /> {t("back")}
      </button>
      <div className="page-head">
        <h1 className="page-h">
          <Heart size={24} /> {t("favs")}
        </h1>
        <span className="mono muted">{t("items", { n: items.length })}</span>
      </div>
      {items.length === 0 ? (
        <div className="state">
          <Heart size={32} strokeWidth={1.3} />
          <p>{t("favEmpty")}</p>
          <button className="btn-primary" onClick={onBack}>
            {t("browse")}
          </button>
        </div>
      ) : (
        <div className="grid">
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
        </div>
      )}
    </main>
  );
}

export default Wishlist;
