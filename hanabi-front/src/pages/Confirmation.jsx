/** Confirmation de commande.
 *
 * La commande passee est le seul moment de la boutique qui merite une vraie
 * celebration : trois salves de feux d'artifice partent en cascade au-dessus
 * de la carte. `burst` respecte `prefers-reduced-motion` et ne fait rien si
 * l'utilisateur a demande a limiter les animations.
 */
import { useEffect } from "react";
import { Check, ArrowRight } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { burst } from "../lib/burst.js";

export function Confirmation({ order, onContinue, loggedIn, onAccount, eur }) {
  const t = useT();
  const items = order.items.reduce((s, l) => s + l.qty, 0);

  useEffect(() => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    // Trois foyers decales dans le temps : l'oeil suit la cascade.
    const shots = [
      [w * 0.5, h * 0.3, 0],
      [w * 0.25, h * 0.4, 260],
      [w * 0.75, h * 0.38, 480],
    ];
    const timers = shots.map(([x, y, delay]) =>
      setTimeout(() => burst(x, y, { count: 40, power: 10 }), delay),
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <main className="done">
      <div className="done-card">
        <div className="done-tick">
          <Check size={30} strokeWidth={3} />
        </div>
        <h1>{t("confirmed")}</h1>
        <p>{t("recapMail", { email: order.email })}</p>
        <div className="done-grid">
          <div>
            <span className="mono small muted">{t("orderLbl")}</span>
            <div className="mono">{order.number}</div>
          </div>
          <div>
            <span className="mono small muted">{t("articles")}</span>
            <div className="mono">{items}</div>
          </div>
          <div>
            <span className="mono small muted">{t("total")}</span>
            <div className="mono">{eur(order.total_cents)}</div>
          </div>
        </div>
        <div className="done-actions">
          <button className="btn-primary" onClick={onContinue}>
            {t("continueShop")} <ArrowRight size={16} />
          </button>
          {loggedIn && (
            <button className="btn-ghost" onClick={onAccount}>
              {t("seeOrders")}
            </button>
          )}
        </div>
      </div>
    </main>
  );
}

export default Confirmation;
