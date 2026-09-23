/** Back-office : pilotage et gestion de la boutique. */
import { useState, useEffect, useCallback } from "react";
import { setToken } from "../lib/api.js";
import { LogoMark } from "../components/brand/LogoMark.jsx";
import { api } from "./api.js";
import { Ico, Chargement } from "./ui.jsx";
import { Dashboard } from "./views/Dashboard.jsx";
import { Analytics } from "./views/Analytics.jsx";
import { Warehouse } from "./views/Warehouse.jsx";
import { Exploitation } from "./views/Exploitation.jsx";
import { Products } from "./views/Products.jsx";
import { Promos } from "./views/Promos.jsx";
import { Orders } from "./views/Orders.jsx";
import { Users } from "./views/Users.jsx";
import "./admin.css";

const GROUPES = [
  {
    titre: "Piloter",
    items: [
      { key: "dashboard", label: "Tableau de bord" },
      { key: "analytics", label: "Analytique" },
      { key: "warehouse", label: "Entrepôt" },
      { key: "exploitation", label: "Exploitation" },
    ],
  },
  {
    titre: "Gérer",
    items: [
      { key: "products", label: "Produits" },
      { key: "promos", label: "Codes promo" },
      { key: "orders", label: "Commandes" },
      { key: "users", label: "Clients" },
    ],
  },
];

const TITRES = {
  dashboard: "Tableau de bord",
  analytics: "Analytique",
  warehouse: "Entrepôt décisionnel",
  exploitation: "Exploitation",
  products: "Produits",
  promos: "Codes promo",
  orders: "Commandes",
  users: "Clients",
};

const CLE_THEME = "hanabi:admin-theme";

export default function Admin() {
  const [tab, setTab] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [products, setProducts] = useState([]);
  const [promos, setPromos] = useState([]);
  const [users, setUsers] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [err, setErr] = useState(null);
  // Identite du compte, pour l'affichage seulement : le serveur refuse les
  // ecritures du compte de demonstration.
  const [me, setMe] = useState(null);
  const readonly = me?.readonly === true;

  // Theme propre au back-office : on ne travaille pas des heures dans la
  // lumiere ou l'on parcourt un catalogue. A defaut de choix, le systeme.
  const [theme, setTheme] = useState(() => {
    try {
      const garde = localStorage.getItem(CLE_THEME);
      if (garde) return garde;
    } catch {
      /* stockage indisponible */
    }
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    try {
      localStorage.setItem(CLE_THEME, theme);
    } catch {
      /* le theme vaudra le temps de l'onglet */
    }
  }, [theme]);

  const flash = useCallback((msg, type = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2800);
  }, []);

  const load = useCallback(async (t) => {
    setLoading(true);
    setErr(null);
    try {
      if (t === "dashboard") setStats(await api("/admin/stats"));
      if (t === "products") setProducts(await api("/admin/products?include_inactive=true"));
      if (t === "promos") setPromos(await api("/admin/promos"));
      // Les commandes se chargent dans leur écran : recherche et pages côté serveur
      if (t === "users") setAlerts(await api("/admin/alerts"));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(tab);
  }, [tab, load]);

  useEffect(() => {
    api("/admin/whoami")
      .then(setMe)
      // Sans reponse, on suppose des droits complets : le serveur tranchera
      .catch(() => setMe({ readonly: false }));
  }, []);

  return (
    <div className="adm" data-theme={theme}>
      {/* La barre latérale est en laque dans les deux thèmes, comme le pied de page de la boutique */}
      <aside className="adm-nav" data-theme="dark">
        <a className="adm-logo" href="/" aria-label="Hanabi, voir la boutique">
          <LogoMark size={30} className="adm-logo-mark" />
          <span className="adm-logo-txt">
            HANABI
            <small>Back-office</small>
          </span>
        </a>

        <nav className="adm-nav-groupes" aria-label="Sections du back-office">
          {GROUPES.map((groupe) => (
            <div key={groupe.titre} className="adm-nav-groupe">
              <span className="adm-nav-titre">{groupe.titre}</span>
              {groupe.items.map((item) => (
                <button
                  key={item.key}
                  className={"adm-nav-btn" + (tab === item.key ? " on" : "")}
                  onClick={() => setTab(item.key)}
                  aria-current={tab === item.key ? "page" : undefined}
                >
                  <Ico nom={item.key} />
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="adm-nav-foot">
          <button
            className="adm-nav-btn"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            aria-label={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
          >
            <Ico nom={theme === "dark" ? "clair" : "sombre"} />
            {theme === "dark" ? "Thème clair" : "Thème sombre"}
          </button>
          <a href="/" className="adm-nav-btn">
            <Ico nom="retour" /> Voir la boutique
          </a>
          {/* Retour a l'accueil : rester sur /admin deconnecte n'afficherait
              qu'une cascade de refus. */}
          <button
            className="adm-nav-btn"
            onClick={() => {
              setToken(null);
              window.location.href = "/";
            }}
          >
            <Ico nom="quitter" /> Se déconnecter
          </button>
          {me?.email && <span className="adm-compte">{me.email}</span>}
        </div>
      </aside>

      <main className="adm-main">
        <div className="adm-topbar">
          <h1 className="adm-title">{TITRES[tab]}</h1>
          {loading && <span className="adm-spin" role="status" aria-label="Chargement" />}
        </div>

        {err && (
          <div className="adm-err" role="alert">
            <strong>{err}</strong>
            <span>
              Si l&apos;erreur mentionne une colonne manquante, la base locale est antérieure au
              schéma : arrête le serveur, supprime atelier.db et relance.
            </span>
          </div>
        )}

        {readonly && (
          <div className="adm-warn adm-readonly">
            Compte de démonstration : le back-office est entièrement consultable, mais les
            modifications sont désactivées.
          </div>
        )}

        {tab === "dashboard" && stats && <Dashboard stats={stats} />}
        {tab === "dashboard" && !stats && !err && (
          <Chargement>Chargement du tableau de bord</Chargement>
        )}
        {tab === "analytics" && <Analytics flash={flash} />}
        {tab === "warehouse" && <Warehouse flash={flash} />}
        {tab === "exploitation" && <Exploitation />}
        {tab === "products" && (
          <Products
            items={products}
            flash={flash}
            readonly={readonly}
            reload={() => load("products")}
          />
        )}
        {tab === "promos" && (
          <Promos items={promos} flash={flash} readonly={readonly} reload={() => load("promos")} />
        )}
        {tab === "orders" && <Orders flash={flash} readonly={readonly} />}
        {tab === "users" && (
          <Users
            items={users}
            setItems={setUsers}
            alerts={alerts}
            flash={flash}
            readonly={readonly}
          />
        )}
      </main>

      <div className="adm-toast-zone" role="status" aria-live="polite">
        {toast && (
          <div className={"adm-toast" + (toast.type === "err" ? " err" : "")}>{toast.msg}</div>
        )}
      </div>
    </div>
  );
}
