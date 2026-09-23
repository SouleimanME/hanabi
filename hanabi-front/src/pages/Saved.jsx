/** Articles mis de cote depuis le panier. En lignes, comme le panier dont ils
 *  sortent : ce sont des achats en attente, pas une vitrine. */
import { ArrowLeft, Trash2 } from "lucide-react";
import { PictoPanier } from "../components/brand/Pictos.jsx";
import { useT } from "../i18n/context.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { StockBadge } from "../components/ui/StockBadge.jsx";

export function Saved({ items, onOpen, onMoveToCart, onRemove, onBack, eur }) {
  const t = useT();

  return (
    <main id="contenu" className="wrap page">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" /> {t("back")}
      </button>
      <div className="page-head">
        <h1 className="page-title">{t("saved")}</h1>
        <span className="muted">{t("itemsN", { n: items.length })}</span>
      </div>

      {items.length === 0 ? (
        <div className="empty">
          <p>{t("savedEmpty")}</p>
          <button className="btn btn-primary" onClick={onBack}>
            {t("browse")}
          </button>
        </div>
      ) : (
        <ul className="lines lines-page">
          {items.map((p) => (
            <li className="line" key={p.id}>
              <button className="line-art" onClick={() => onOpen(p)} aria-label={p.name}>
                <ProductArt art={p.art} />
              </button>
              <div className="line-main">
                <div className="line-top">
                  <button className="line-name link-plain" onClick={() => onOpen(p)}>
                    {p.name}
                  </button>
                  <span className="price">{eur(p.price_cents)}</span>
                </div>
                <span className="code">{p.code}</span>
                <StockBadge stock={p.stock} />
                {/* Un article epuise pendant l'attente reste visible, bouton inactif */}
                <div className="line-actions">
                  <button
                    className="btn btn-quiet btn-sm"
                    onClick={() => onMoveToCart(p.id)}
                    disabled={p.stock === 0}
                  >
                    <PictoPanier taille={16} /> {t("moveToCart")}
                  </button>
                  <button
                    className="icon-btn"
                    onClick={() => onRemove(p.id)}
                    aria-label={t("removeNamed", { name: p.name })}
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

export default Saved;
