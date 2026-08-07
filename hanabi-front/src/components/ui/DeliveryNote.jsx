/** Date de livraison estimee, affichee la ou la question se pose.
 *
 * Sur la fiche produit et dans le panier : ce sont les deux moments ou l'on
 * hesite, et « est-ce que ce sera la a temps » est la question qui reste sans
 * reponse quand on n'annonce qu'un delai.
 */
import { Truck } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import {
  CUTOFF_HOUR,
  estimateDelivery,
  formatDeliveryDate,
  isBeforeCutoff,
} from "../../lib/delivery.js";

export function DeliveryNote({ lang }) {
  const t = useT();
  const now = new Date();
  const date = formatDeliveryDate(estimateDelivery(now), lang);

  // Avant l'heure limite, la date s'accompagne de sa condition : c'est une
  // raison de commander maintenant, et elle est vraie.
  const key = isBeforeCutoff(now) ? "deliveryCutoff" : "deliveryBy";

  return (
    <span className="delivery-note">
      <Truck size={14} />
      <span>{t(key, { date, hour: CUTOFF_HOUR })}</span>
    </span>
  );
}
