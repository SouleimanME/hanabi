/** Jauge de progression vers la livraison offerte.
 *
 * Un chiffre seul ("plus que 12 €") se lit ; une barre qui se remplit se
 * ressent. C'est le levier de panier moyen le plus efficace d'une boutique :
 * l'utilisateur voit concretement ce qui lui manque, et la barre celebre le
 * franchissement du seuil.
 *
 * Le montant retenu est le sous-total remise deduite, pour rester coherent
 * avec le calcul du backend (`app/pricing.py`).
 */
import { Truck, Check } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { FREE_SHIPPING_CENTS } from "../../lib/constants.js";

export function ShippingGauge({ subtotalCents, discountCents = 0, eur }) {
  const t = useT();
  const net = Math.max(0, subtotalCents - discountCents);
  const missing = FREE_SHIPPING_CENTS - net;
  const unlocked = missing <= 0;
  const pct = Math.min(100, (net / FREE_SHIPPING_CENTS) * 100);

  return (
    <div className={"gauge" + (unlocked ? " done" : "")}>
      <div className="gauge-top">
        {unlocked ? (
          <>
            <Check size={14} strokeWidth={3} />
            <strong>{t("shipUnlocked")}</strong>
          </>
        ) : (
          <>
            <Truck size={14} />
            <span>{t("shipHint", { x: eur(missing) })}</span>
          </>
        )}
      </div>
      <div
        className="gauge-track"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={t("shipGaugeLabel")}
      >
        <div className="gauge-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
