/** Etat du stock, en texte et en marque : jamais par la couleur seule. */
import { useT } from "../../i18n/context.jsx";

export function StockBadge({ stock, quiet = false }) {
  const t = useT();
  if (stock === 0) return <span className="stock stock-out">{t("sold")}</span>;
  if (stock <= 4) return <span className="stock stock-low">{t("onlyN", { n: stock })}</span>;
  if (quiet) return null;
  return <span className="stock">{t("inStock")}</span>;
}
