/** Compte client : informations personnelles et historique de commandes. */
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  User,
  LogOut,
  ReceiptText,
  Package,
  ContactRound,
  MailWarning,
  CreditCard,
  ShieldCheck,
  Pencil,
  DatabaseZap,
} from "lucide-react";
import { useT } from "../i18n/context.jsx";
import { Auth } from "../lib/api.js";
import { ProductArt } from "../components/brand/ProductArt.jsx";
import { Kamon } from "../components/brand/Ornaments.jsx";
import { useReveal } from "../hooks/useReveal.js";
import { InfosForm } from "../components/account/InfosForm.jsx";
import { Paiements } from "../components/account/Paiements.jsx";
import { Securite } from "../components/account/Securite.jsx";
import { MesDonnees } from "../components/account/MesDonnees.jsx";

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

/** Rappel d'adresse non confirmee, avec de quoi renvoyer le lien.
 *
 * SANS CE BLOC, le drapeau `email_verified` ne servait a rien : le serveur le
 * calculait, l'API le renvoyait, et personne ne le lisait. La route de renvoi
 * existait elle aussi sans qu'aucun ecran ne l'appelle - un parcours complet
 * cote serveur, et aucune porte pour y entrer.
 *
 * Le ton reste bas volontairement. Le compte fonctionne sans confirmation, et
 * une alerte rouge sur un compte qui marche apprend surtout a ignorer les
 * alertes. C'est un rappel, pas un avertissement.
 */
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
    <div className="acc-verif" role="status">
      <MailWarning size={17} />
      <div>
        <p>{t("verifPending")}</p>
        {etat === "envoye" ? (
          <p className="acc-verif-ok">{t("verifResent")}</p>
        ) : (
          <button
            className="lien-oubli acc-verif-lien"
            onClick={renvoyer}
            disabled={etat === "envoi"}
          >
            {etat === "envoi" ? "…" : etat === "echec" ? t("verifRetry") : t("verifResend")}
          </button>
        )}
      </div>
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
  const infosRef = useRef(null);
  const ordersRef = useRef(null);
  const paiementsRef = useRef(null);
  const securiteRef = useRef(null);
  const donneesRef = useRef(null);
  const [edition, setEdition] = useState(false);

  // Le menu ouvre le compte sur une section precise (« Mes informations »,
  // « Mes commandes ») : sans ce recentrage, les deux entrees menaient au meme
  // haut de page et paraissaient ne rien faire. La demande porte un
  // horodatage, si bien que deux clics sur la meme entree rejouent le
  // deplacement au lieu de rester lettre morte.
  useEffect(() => {
    const refs = {
      infos: infosRef,
      orders: ordersRef,
      paiements: paiementsRef,
      securite: securiteRef,
      donnees: donneesRef,
    };
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

      <BandeauVerification user={user} />

      <h2 className="acc-sub" ref={infosRef}>
        <ContactRound size={18} /> {t("myInfo")}
        {!edition && (
          <button className="lien-oubli acc-modifier" onClick={() => setEdition(true)}>
            <Pencil size={13} /> {t("edit")}
          </button>
        )}
      </h2>
      {edition ? (
        <div className="info-card">
          <InfosForm
            user={user}
            onEnregistre={(profil) => {
              onProfil?.(profil);
              setEdition(false);
              flash?.(t("infoSaved"));
            }}
            onAnnuler={() => setEdition(false)}
          />
        </div>
      ) : (
        <div className="info-card">
          <InfoRow label={t("civility")} value={civility} />
          <InfoRow label={t("fullName")} value={user.name} />
          <InfoRow label={t("email")} value={user.email} />
          <InfoRow label={t("birthdate")} value={user.birthdate} />
          <InfoRow label={t("phone")} value={user.phone} />
          <InfoRow label={t("adresse")} value={address} />
        </div>
      )}

      <h2 className="acc-sub" ref={paiementsRef}>
        <CreditCard size={18} /> {t("myPayments")}
      </h2>
      <div className="info-card">
        <Paiements flash={flash} />
      </div>

      <h2 className="acc-sub" ref={securiteRef}>
        <ShieldCheck size={18} /> {t("mySecurity")}
      </h2>
      <div className="info-card">
        <Securite user={user} onProfil={onProfil} flash={flash} />
      </div>

      <h2 className="acc-sub" ref={donneesRef}>
        <DatabaseZap size={18} /> {t("myData")}
      </h2>
      <div className="info-card">
        <MesDonnees user={user} onEfface={onEfface} flash={flash} />
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
