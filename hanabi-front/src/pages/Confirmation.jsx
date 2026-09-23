/** Confirmation de commande : ce qui a ete commande, et la suite. */
import { Check, ArrowRight } from "lucide-react";
import { useT } from "../i18n/context.jsx";

export function Confirmation({ order, onContinue, loggedIn, onAccount, eur }) {
  const t = useT();
  const articles = order.items.reduce((s, l) => s + l.qty, 0);

  return (
    <main id="contenu" className="wrap page">
      <section className="token-card" aria-labelledby="confirmation-titre">
        <span className="token-mark" aria-hidden="true">
          <Check size={28} strokeWidth={2.4} />
        </span>
        <h1 id="confirmation-titre">{t("confirmed")}</h1>
        <p>{t("recapMail", { email: order.email })}</p>
        <dl className="order-facts">
          <div>
            <dt>{t("orderLbl")}</dt>
            <dd className="code">{order.number}</dd>
          </div>
          <div>
            <dt>{t("articles")}</dt>
            <dd className="tabular">{articles}</dd>
          </div>
          <div>
            <dt>{t("total")}</dt>
            <dd className="price">{eur(order.total_cents)}</dd>
          </div>
        </dl>
        <div className="actions actions-center">
          <button className="btn btn-primary" onClick={onContinue}>
            {t("continueShop")} <ArrowRight size={18} aria-hidden="true" />
          </button>
          {loggedIn && (
            <button className="btn btn-quiet" onClick={onAccount}>
              {t("seeOrders")}
            </button>
          )}
        </div>
      </section>
    </main>
  );
}

export default Confirmation;
