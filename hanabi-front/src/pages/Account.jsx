/** Compte client : informations personnelles et historique de commandes. */
import { useEffect, useRef } from "react";
import { ArrowLeft, User, LogOut, ReceiptText, Package, ContactRound } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { Kamon } from "../components/brand/Ornaments.jsx";
import { useReveal } from "../hooks/useReveal.js";

/** Une commande de l'historique, revelee a son entree dans le champ de vision.
 *
 * Extrait en composant pour que chaque carte porte son propre observateur : un
 * hook ne peut pas etre appele dans une boucle du composant parent.
 */
function OrderCard({ order, index, eur }) {
  const t = useT();
  const [ref, visible] = useReveal({ threshold: 0.1 });
  const count = order.items.reduce((sum, line) => sum + line.qty, 0);

  return (
    <div
      ref={ref}
      className={"order reveal" + (visible ? " in" : "")}
      style={{ transitionDelay: `${Math.min(index, 6) * 70}ms` }}
    >
      <div className="order-hd">
        <div>
          <span className="mono order-num">{order.number}</span>
          <span className="muted small order-date">
            {new Date(order.created_at).toLocaleDateString()}
          </span>
        </div>
        <div className="order-hd-r">
          <span className="order-count small muted">{t("articlesN", { n: count })}</span>
          <span className="mono price">{eur(order.total_cents)}</span>
        </div>
      </div>
      <div className="order-items">
        {order.items.map((line, i) => (
          <div className="order-item" key={i}>
            <div className="order-thumb">
              <ProductArt art={line.art} small />
            </div>
            <span className="order-name">{line.name}</span>
            <span className="mono small muted">× {line.qty}</span>
            <span className="mono small">{eur(line.unit_price_cents * line.qty)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Une ligne du bloc d'informations. Un champ vide est tu plutot qu'affiche
 *  vide : les coordonnees sont facultatives a l'inscription. */
function InfoRow({ label, value }) {
  if (!value) return null;
  return (
    <div className="info-row">
      <span className="info-label">{label}</span>
      <span className="info-value">{value}</span>
    </div>
  );
}

export function Account({ user, orders, section, onLogout, onBack, eur }) {
  const t = useT();
  const infosRef = useRef(null);
  const ordersRef = useRef(null);

  // Le menu ouvre le compte sur une section precise (« Mes informations »,
  // « Mes commandes ») : sans ce recentrage, les deux entrees menaient au meme
  // haut de page et paraissaient ne rien faire. La demande porte un
  // horodatage, si bien que deux clics sur la meme entree rejouent le
  // deplacement au lieu de rester lettre morte.
  useEffect(() => {
    const refs = { infos: infosRef, orders: ordersRef };
    refs[section?.name]?.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [section]);

  const civility = user.civility ? t("civ" + user.civility) : null;
  const address = [user.addr, user.addr_extra, [user.cp, user.city].filter(Boolean).join(" ")]
    .filter(Boolean)
    .join(", ");

  return (
    <main className="pp acc">
      <Kamon size={300} />
      <button className="back" onClick={onBack}>
        <ArrowLeft size={16} /> {t("back")}
      </button>
      <div className="page-head">
        <h1 className="page-h">
          <User size={24} /> {user.name}
        </h1>
        <button className="btn-ghost" onClick={onLogout}>
          <LogOut size={15} /> {t("logout")}
        </button>
      </div>
      <p className="muted acc-mail mono">{user.email}</p>

      <h2 className="acc-sub" ref={infosRef}>
        <ContactRound size={18} /> {t("myInfo")}
      </h2>
      <div className="info-card">
        <InfoRow label={t("civility")} value={civility} />
        <InfoRow label={t("fullName")} value={user.name} />
        <InfoRow label={t("email")} value={user.email} />
        <InfoRow label={t("birthdate")} value={user.birthdate} />
        <InfoRow label={t("phone")} value={user.phone} />
        <InfoRow label={t("adresse")} value={address} />
        <p className="info-note muted small">{t("infoNote")}</p>
      </div>

      <h2 className="acc-sub" ref={ordersRef}>
        <ReceiptText size={18} /> {t("myOrders")}
        {orders.length > 0 && <span className="mono small muted">({orders.length})</span>}
      </h2>
      {orders.length === 0 ? (
        <div className="state sm">
          <Package size={28} strokeWidth={1.3} />
          <p>{t("noOrders")}</p>
        </div>
      ) : (
        <div className="orders">
          {orders.map((order, i) => (
            <OrderCard key={order.number} order={order} index={i} eur={eur} />
          ))}
        </div>
      )}
    </main>
  );
}

export default Account;
