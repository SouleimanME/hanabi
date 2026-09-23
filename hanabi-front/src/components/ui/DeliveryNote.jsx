/** Date de livraison estimee, la ou la question se pose : fiche, panier,
 *  paiement. Avant l'heure limite, la date s'accompagne de sa condition. */
import { Truck } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import {
  CUTOFF_HOUR,
  estimateDelivery,
  formatDeliveryDate,
  isBeforeCutoff,
} from "../../lib/delivery.js";

export function DeliveryNote({ lang, icone = true }) {
  const t = useT();
  const now = new Date();
  const date = formatDeliveryDate(estimateDelivery(now), lang);
  const key = isBeforeCutoff(now) ? "deliveryCutoff" : "deliveryBy";

  return (
    <span className="delivery-note">
      {icone && <Truck size={16} aria-hidden="true" />}
      <span>{t(key, { date, hour: CUTOFF_HOUR })}</span>
    </span>
  );
}
