/** Pastille d'etat du stock : epuise, presque epuise, disponible. */
import { Package } from "lucide-react";
import { useT } from "../../i18n/context.jsx";

export function StockBadge({ stock }) {
  const t = useT();
  if (stock === 0)
    return (
      <span className="stock out">
        <Package size={13} /> {t("sold")}
      </span>
    );
  if (stock <= 4)
    return (
      <span className="stock low">
        <Package size={13} /> {t("onlyN", { n: stock })}
      </span>
    );
  return (
    <span className="stock ok">
      <Package size={13} /> {t("inStock")}
    </span>
  );
}
