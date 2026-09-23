/** Sous-total, remise, livraison et total, communs au panier et au paiement. */
import { useT } from "../../i18n/context.jsx";

export function Totals({ disp, eur }) {
  const t = useT();
  return (
    <dl className="totals">
      <div>
        <dt>{t("subtotal")}</dt>
        <dd>{eur(disp.subtotal_cents)}</dd>
      </div>
      {disp.discount_cents > 0 && (
        <div>
          <dt>{t("discount")}</dt>
          <dd>−{eur(disp.discount_cents)}</dd>
        </div>
      )}
      <div>
        <dt>{t("shipping")}</dt>
        <dd>{disp.shipping_cents === 0 ? t("free") : eur(disp.shipping_cents)}</dd>
      </div>
      <div className="totals-total">
        <dt>{t("total")}</dt>
        <dd aria-live="polite">{eur(disp.total_cents)}</dd>
      </div>
    </dl>
  );
}
