/** Articles mis de cote depuis le panier (voir hooks/useSaved.js).
 *
 * Presentation en lignes plutot qu'en grille de fiches, comme le panier dont
 * ces articles sortent : ce sont des achats en attente, pas une vitrine.
 */
import { ArrowLeft, Bookmark, ShoppingBag, Trash2 } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { StockBadge } from "../components/ui/StockBadge.jsx";

export function Saved({ items, onOpen, onMoveToCart, onRemove, onBack, eur }) {
  const t = useT();

  return (
    <main className="pp">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={16} /> {t("back")}
      </button>
      <div className="page-head">
        <h1 className="page-h">
          <Bookmark size={24} /> {t("saved")}
        </h1>
        <span className="mono muted">{t("items", { n: items.length })}</span>
      </div>

      {items.length === 0 ? (
        <div className="state">
          <Bookmark size={32} strokeWidth={1.3} />
          <p>{t("savedEmpty")}</p>
          <button className="btn-primary" onClick={onBack}>
            {t("browse")}
          </button>
        </div>
      ) : (
        <div className="saved-list">
          {items.map((p) => (
            <div className="saved-line" key={p.id}>
              <button className="saved-thumb" onClick={() => onOpen(p)} aria-label={p.name}>
                <ProductArt art={p.art} small />
              </button>
              <div className="saved-info">
                <button className="saved-name" onClick={() => onOpen(p)}>
                  {p.name}
                </button>
                <span className="mono small muted">{p.code}</span>
                <StockBadge stock={p.stock} />
              </div>
              <div className="saved-act">
                <span className="mono price">{eur(p.price_cents)}</span>
                <div className="saved-btns">
                  {/* Un article epuise pendant son attente reste visible, mais
                      son bouton se desactive : le retirer d'office ferait
                      disparaitre sans explication ce qu'on avait mis de cote. */}
                  <button
                    className="btn-primary sm"
                    onClick={() => onMoveToCart(p.id)}
                    disabled={p.stock === 0}
                  >
                    <ShoppingBag size={15} /> {t("moveToCart")}
                  </button>
                  <button
                    className="icon-btn"
                    onClick={() => onRemove(p.id)}
                    aria-label={t("removeC")}
                    title={t("removeC")}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

export default Saved;
