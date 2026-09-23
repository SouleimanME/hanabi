/** Compte client : informations, paiements, securite, donnees, commandes. */
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, LogOut, MailWarning, Pencil } from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { Auth } from "../lib/api.js";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { InfosForm } from "../components/account/InfosForm.jsx";
import { Paiements } from "../components/account/Paiements.jsx";
import { Securite } from "../components/account/Securite.jsx";
import { MesDonnees } from "../components/account/MesDonnees.jsx";

function Commande({ order, eur }) {
  const t = useT();
  const articles = order.items.reduce((sum, line) => sum + line.qty, 0);

  return (
    <li className="order">
      <div className="order-head">
        <div>
          <span className="code">{order.number}</span>
          <span className="muted">{new Date(order.created_at).toLocaleDateString()}</span>
        </div>
        <div className="order-sum">
          <span className="muted">{t("articlesN", { n: articles })}</span>
          <span className="price">{eur(order.total_cents)}</span>
        </div>
      </div>
      <ul className="order-items">
        {order.items.map((line, i) => (
          <li key={i}>
            <span className="order-art">
              <ProductArt art={line.art} />
            </span>
            <span className="order-name">{line.name}</span>
            <span className="muted tabular">× {line.qty}</span>
            <span className="price">{eur(line.unit_price_cents * line.qty)}</span>
          </li>
        ))}
      </ul>
    </li>
  );
}

/** Rappel d'adresse non confirmee. */
function BandeauVerification({ user }) {
  const t = useT();
  const [etat, setEtat] = useState("repos"); // repos | envoi | envoye | echec

  if (user.email_verified) return null;

  const renvoyer = async () => {
    setEtat("envoi");
    try {
      await Auth.resendVerification();
      setEtat("envoye");
    } catch {
      setEtat("echec");
    }
  };

  return (
    <div className="notice" role="status">
      <MailWarning size={18} aria-hidden="true" />
      <div>
        <p>{t("verifPending")}</p>
        {etat === "envoye" ? (
          <p>{t("verifResent")}</p>
        ) : (
          <button className="link" onClick={renvoyer} disabled={etat === "envoi"}>
            {etat === "echec" ? t("verifRetry") : t("verifResend")}
          </button>
        )}
      </div>
    </div>
  );
}

function Ligne({ label, value }) {
  if (!value) return null;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function Account({
  user,
  orders,
  section,
  onLogout,
  onBack,
  eur,
  onProfil,
  onEfface,
  flash,
}) {
  const t = useT();
  const refs = {
    infos: useRef(null),
    paiements: useRef(null),
    securite: useRef(null),
    donnees: useRef(null),
    orders: useRef(null),
  };
  const [edition, setEdition] = useState(false);

  // Le menu ouvre le compte sur une section ; l'horodatage de la demande
  // rejoue le deplacement si l'on choisit deux fois la meme.
  useEffect(() => {
    refs[section?.name]?.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section]);

  const civilite = user.civility ? t("civ" + user.civility) : null;
  const adresse = [user.addr, user.addr_extra, [user.cp, user.city].filter(Boolean).join(" ")]
    .filter(Boolean)
    .join(", ");

  return (
    <main id="contenu" className="wrap page account">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} aria-hidden="true" /> {t("back")}
      </button>
      <div className="page-head">
        <div>
          <h1 className="page-title">{user.name}</h1>
          <p className="muted">{user.email}</p>
        </div>
        <button className="btn btn-quiet" onClick={onLogout}>
          <LogOut size={16} aria-hidden="true" /> {t("logout")}
        </button>
      </div>

      <BandeauVerification user={user} />

      <section className="account-section" ref={refs.infos} aria-labelledby="compte-infos">
        <div className="section-head">
          <h2 id="compte-infos">{t("myInfo")}</h2>
          {!edition && (
            <button className="btn btn-quiet btn-sm" onClick={() => setEdition(true)}>
              <Pencil size={14} aria-hidden="true" /> {t("edit")}
            </button>
          )}
        </div>
        <div className="panel">
          {edition ? (
            <InfosForm
              user={user}
              onEnregistre={(profil) => {
                onProfil?.(profil);
                setEdition(false);
                flash?.(t("infoSaved"));
              }}
              onAnnuler={() => setEdition(false)}
            />
          ) : (
            <dl className="facts">
              <Ligne label={t("civility")} value={civilite} />
              <Ligne label={t("fullName")} value={user.name} />
              <Ligne label={t("email")} value={user.email} />
              <Ligne label={t("birthdate")} value={user.birthdate} />
              <Ligne label={t("phone")} value={user.phone} />
              <Ligne label={t("adresse")} value={adresse} />
            </dl>
          )}
        </div>
      </section>

      <section className="account-section" ref={refs.paiements} aria-labelledby="compte-paiements">
        <div className="section-head">
          <h2 id="compte-paiements">{t("myPayments")}</h2>
        </div>
        <div className="panel">
          <Paiements flash={flash} />
        </div>
      </section>

      <section className="account-section" ref={refs.securite} aria-labelledby="compte-securite">
        <div className="section-head">
          <h2 id="compte-securite">{t("mySecurity")}</h2>
        </div>
        <div className="panel">
          <Securite user={user} onProfil={onProfil} flash={flash} />
        </div>
      </section>

      <section className="account-section" ref={refs.donnees} aria-labelledby="compte-donnees">
        <div className="section-head">
          <h2 id="compte-donnees">{t("myData")}</h2>
        </div>
        <div className="panel">
          <MesDonnees user={user} onEfface={onEfface} flash={flash} />
        </div>
      </section>

      <section className="account-section" ref={refs.orders} aria-labelledby="compte-commandes">
        <div className="section-head">
          <h2 id="compte-commandes">
            {t("myOrders")}
            {orders.length > 0 && <span className="section-count">{orders.length}</span>}
          </h2>
        </div>
        {orders.length === 0 ? (
          <div className="empty">
            <p>{t("noOrders")}</p>
          </div>
        ) : (
          <ul className="orders">
            {orders.map((order) => (
              <Commande key={order.number} order={order} eur={eur} />
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

export default Account;
