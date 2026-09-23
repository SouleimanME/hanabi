/** Distance a la livraison offerte, en texte et en barre. */
import { Truck, Check } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { FREE_SHIPPING_CENTS } from "../../lib/constants.js";

export function ShippingGauge({ subtotalCents, discountCents = 0, eur }) {
  const t = useT();
  const net = Math.max(0, subtotalCents - discountCents);
  const manque = FREE_SHIPPING_CENTS - net;
  const atteint = manque <= 0;
  const pct = Math.min(100, (net / FREE_SHIPPING_CENTS) * 100);

  return (
    <div className="gauge" data-done={atteint}>
      <p className="gauge-text">
        {atteint ? (
          <>
            <Check size={16} aria-hidden="true" /> {t("shipUnlocked")}
          </>
        ) : (
          <>
            <Truck size={16} aria-hidden="true" /> {t("shipHint", { x: eur(manque) })}
          </>
        )}
      </p>
      <div
        className="gauge-track"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={t("shipGaugeLabel")}
      >
        <div className="gauge-fill" style={{ transform: `scaleX(${pct / 100})` }} />
      </div>
    </div>
  );
}
