/** Back-office : catalogue, promotions, commandes et clients.
 *
 * Le back-office est monolingue (francais) et sans traduction : il s'adresse
 * a l'equipe de la boutique, pas aux clients. Il partage le jeton
 * d'authentification de la boutique, mais chaque route /admin verifie cote
 * serveur que le compte porte bien le drapeau administrateur.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { API_BASE, getToken, setToken } from "../lib/api.js";
import { createPriceFormatter } from "../lib/format.js";
import { MAIN_SIZE, toCanonicalMain, toGalleryImage } from "./image.js";
import { axisEuro, heatColor } from "./chart-utils.js";
import { BarChart, DonutChart, HeatScale, LineChart } from "./charts.jsx";
import { SERIES } from "./palette.js";
import "./admin.css";

const BASE = API_BASE;
const eur = createPriceFormatter("fr");
const fmtDate = (s) =>
  new Date(s).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });

async function api(path, opts = {}) {
  const token = getToken();
  const res = await fetch(BASE + path, {
    method: opts.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Erreur ${res.status}`);
  return data;
}

/** Telecharge un fichier servi par une route protegee.
 *
 * Un simple lien ne convient pas : le navigateur n'y joint pas l'en-tete
 * Authorization, et la route repondrait 401. On recupere donc le corps avec le
 * jeton, puis on declenche le telechargement depuis un objet blob.
 *
 * Le nom de fichier est celui propose par le serveur (Content-Disposition),
 * pour qu'il reste decide en un seul endroit.
 */
async function download(path, fallbackName) {
  const token = getToken();
  const res = await fetch(BASE + path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Erreur ${res.status}`);
  }

  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = match ? match[1] : fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Libere la memoire retenue par le blob.
  URL.revokeObjectURL(url);
}

// Infobulle des commandes desactivees pour le compte vitrine. Le refus reel
// vient du serveur ; ceci evite seulement de cliquer pour rien.
const LECTURE_SEULE = "Compte de démonstration : modification désactivée";

const CATS = ["Compagnons", "Tradition", "Collection"];
const SHAPES = [
  "enso",
  "wave",
  "fan",
  "asanoha",
  "torii",
  "moon",
  "sakura",
  "bol",
  "baguettes",
  "neko",
];
const PALETTE = [SERIES[0], "#16140F", SERIES[1], "#C9A24B", SERIES[2], "#E8DFC9", "#9C6B3B"];

/* ================================================================== */
/* App Admin                                                          */
/* ================================================================== */
export default function Admin() {
  const [tab, setTab] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [products, setProducts] = useState([]);
  const [promos, setPromos] = useState([]);
  const [orders, setOrders] = useState([]);
  const [users, setUsers] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [err, setErr] = useState(null);
  // Identite du compte connecte. Sert uniquement a l'affichage : c'est le
  // serveur qui refuse les ecritures du compte de demonstration.
  const [me, setMe] = useState(null);
  const readonly = me?.readonly === true;

  // Thème du back-office, indépendant de celui de la boutique : on ne travaille
  // pas huit heures dans la même lumière qu'on parcourt un catalogue. Le choix
  // est mémorisé ; à défaut, on suit la préférence du système plutôt que
  // d'imposer le sombre à quelqu'un qui a réglé sa machine autrement.
  const [theme, setTheme] = useState(() => {
    try {
      const garde = localStorage.getItem("hanabi:admin-theme");
      if (garde) return garde;
    } catch {
      /* stockage indisponible : on retombe sur la préférence système */
    }
    return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
  });

  useEffect(() => {
    try {
      localStorage.setItem("hanabi:admin-theme", theme);
    } catch {
      /* le thème restera valable le temps de l'onglet */
    }
  }, [theme]);

  const flash = (msg, type = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 2800);
  };

  const load = useCallback(async (t) => {
    setLoading(true);
    setErr(null);
    try {
      if (t === "dashboard") setStats(await api("/admin/stats"));
      if (t === "products") setProducts(await api("/admin/products?include_inactive=true"));
      if (t === "promos") setPromos(await api("/admin/promos"));
      if (t === "orders") setOrders(await api("/admin/orders?limit=100"));
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
      // Sans reponse, on suppose des droits complets : le serveur tranchera de
      // toute facon. Bloquer l'interface sur l'echec de cet appel accessoire
      // rendrait le back-office inutilisable pour un vrai administrateur.
      .catch(() => setMe({ readonly: false }));
  }, []);

  return (
    <div className="adm" data-theme={theme}>
      <aside className="adm-nav">
        <div className="adm-logo">
          <span className="adm-logo-mark">花</span>
          <span className="adm-logo-txt">
            HANABI
            <small>管理 · back-office</small>
          </span>
        </div>
        {/* Deux groupes nommés plutôt qu'une liste de six entrées : lire et
            gérer ne sont pas la même activité, et un intitulé de section coûte
            moins cher à l'œil qu'un choix parmi six items indifférenciés. */}
        {[
          {
            titre: "Piloter",
            items: [
              { key: "dashboard", label: "Tableau de bord", icon: "◳" },
              { key: "analytics", label: "Analytique", icon: "◫" },
              { key: "warehouse", label: "Entrepôt", icon: "◨" },
            ],
          },
          {
            titre: "Gérer",
            items: [
              { key: "products", label: "Produits", icon: "◰" },
              { key: "promos", label: "Codes promo", icon: "◱" },
              { key: "orders", label: "Commandes", icon: "◲" },
              { key: "users", label: "Clients", icon: "◴" },
            ],
          },
        ].map((groupe) => (
          <div key={groupe.titre} className="adm-nav-groupe">
            <span className="adm-nav-titre">{groupe.titre}</span>
            {groupe.items.map((item) => (
              <button
                key={item.key}
                className={"adm-nav-btn" + (tab === item.key ? " on" : "")}
                onClick={() => setTab(item.key)}
                aria-current={tab === item.key ? "page" : undefined}
              >
                <span className="adm-nav-ic">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        ))}
        <div className="adm-nav-foot">
          <button
            className="adm-theme"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            aria-label={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
            title={theme === "dark" ? "Thème clair" : "Thème sombre"}
          >
            <span className="adm-theme-track">
              <span className="adm-theme-knob">{theme === "dark" ? "☾" : "☀"}</span>
            </span>
            {theme === "dark" ? "Sombre" : "Clair"}
          </button>
          <a href="/" className="adm-nav-btn adm-back">
            <span className="adm-nav-ic">↩</span> Voir le site
          </a>
          {/* Le back-office n'offrait aucun moyen de fermer sa session : il
              fallait retourner sur la boutique pour se déconnecter, en sachant
              que le lien s'y trouve. Sur un poste partagé, c'est un jeton
              d'administration qui reste actif faute d'avoir su où cliquer.

              La redirection vers l'accueil est volontaire : rester sur /admin
              après s'être déconnecté afficherait une page vide et une cascade
              de 401. */}
          <button
            className="adm-nav-btn adm-deconnexion"
            onClick={() => {
              setToken(null);
              window.location.href = "/";
            }}
            title={me?.email ? `Connecté en tant que ${me.email}` : undefined}
          >
            <span className="adm-nav-ic">⏻</span> Se déconnecter
          </button>
          {me?.email && <span className="adm-compte">{me.email}</span>}
        </div>
      </aside>

      <main className="adm-main">
        <div className="adm-topbar">
          <h1 className="adm-title">
            {
              {
                dashboard: "Tableau de bord",
                analytics: "Analytique",
                warehouse: "Entrepôt décisionnel",
                products: "Produits",
                promos: "Codes promo",
                orders: "Commandes",
                users: "Clients",
              }[tab]
            }
          </h1>
          {loading && <span className="adm-spin" />}
        </div>

        {err && (
          <div className="adm-err">
            ⚠ {err}
            <br />
            <span style={{ fontSize: 12, opacity: 0.8 }}>
              Si l&apos;erreur mentionne une colonne manquante (« no such column »), arrête le
              serveur, supprime atelier.db et relance.
            </span>
          </div>
        )}

        {readonly && (
          <div className="adm-warn adm-info adm-readonly">
            👁 Compte de démonstration : le back-office est entièrement consultable, mais les
            modifications sont désactivées.
          </div>
        )}

        {tab === "dashboard" && stats && <Dashboard stats={stats} />}
        {tab === "dashboard" && !stats && !err && (
          <div className="adm-loading">
            <span className="adm-spin" /> Chargement du tableau de bord...
          </div>
        )}
        {/* L'onglet analytique gere son propre chargement : ses quatre vues
            interrogent des routes distinctes, et les charger toutes a
            l'ouverture ferait payer a chacun ce que peu consultent. */}
        {tab === "analytics" && <Analytics flash={flash} />}
        {/* Meme raison que pour l'analytique : cet onglet interroge des routes
            qui lui sont propres, et rien ne justifie de les appeler avant qu'on
            l'ouvre. */}
        {tab === "warehouse" && <Warehouse flash={flash} />}
        {tab === "products" && (
          <Products
            items={products}
            setItems={setProducts}
            flash={flash}
            readonly={readonly}
            reload={() => load("products")}
          />
        )}
        {tab === "promos" && (
          <Promos
            items={promos}
            setItems={setPromos}
            flash={flash}
            readonly={readonly}
            reload={() => load("promos")}
          />
        )}
        {tab === "orders" && (
          <Orders items={orders} flash={flash} readonly={readonly} reload={() => load("orders")} />
        )}
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

      {toast && (
        <div className={"adm-toast" + (toast.type === "err" ? " err" : "")}>{toast.msg}</div>
      )}
    </div>
  );
}

/* ================================================================== */
/* Analytique                                                         */
/* ================================================================== */
const pct = (v) => `${(v * 100).toFixed(1)} %`;
const num = (v) => (v ?? 0).toLocaleString("fr-FR");

const ANALYTICS_VIEWS = [
  { key: "overview", label: "Vue d'ensemble" },
  { key: "profit", label: "Rentabilité" },
  { key: "forecast", label: "Tendance" },
  { key: "cohorts", label: "Cohortes" },
  { key: "segments", label: "Segments" },
  { key: "affinities", label: "Affinités" },
];

const PERIODS = [
  { days: 30, label: "30 jours" },
  { days: 90, label: "90 jours" },
  { days: 365, label: "12 mois" },
];

/** Variation d'un indicateur d'une période à l'autre.
 *
 * `null` n'est pas zéro : il signale qu'aucune comparaison n'est possible
 * parce que la période précédente était vide. Afficher « +100 % » dans ce cas
 * serait faux, et masquer la ligne ferait disparaître l'information.
 */
/** Sens d'une variation, pour teinter la tuile. `null` quand il n'y a rien à
 *  comparer : la tuile garde alors l'accent neutre de la marque. */
function tendance(value, inverse = false) {
  if (value == null) return "neutre";
  const bon = inverse ? value <= 0 : value >= 0;
  return bon ? "hausse" : "baisse";
}

function Delta({ value, inverse = false }) {
  if (value == null) return <span className="delta delta-none">nouveau</span>;
  const bon = inverse ? value <= 0 : value >= 0;
  const signe = value > 0 ? "+" : "";
  return (
    <span className={"delta " + (bon ? "delta-up" : "delta-down")}>
      {signe}
      {(value * 100).toFixed(1)} %
    </span>
  );
}

function Analytics({ flash }) {
  const [view, setView] = useState("overview");
  const [days, setDays] = useState(30);
  const [data, setData] = useState({});
  const [busy, setBusy] = useState(false);

  // Chaque vue a sa route. On garde en mémoire ce qui a déjà été chargé pour
  // qu'un aller-retour entre deux onglets ne relance pas les calculs.
  const routes = {
    overview: `/admin/analytics?months=12&days=${days}`,
    // La rentabilité se sert du même appel que la vue d'ensemble : elle en
    // relit le catalogue plutôt que de refaire calculer les mêmes agrégats.
    profit: `/admin/analytics?months=12&days=${days}`,
    forecast: "/admin/analytics/forecast?months=12&horizon=3",
    cohorts: "/admin/analytics/cohorts?months=12",
    segments: "/admin/analytics/segments",
    affinities: "/admin/analytics/affinities?limit=12",
  };
  const cle = ["overview", "profit"].includes(view) ? `overview:${days}` : view;

  useEffect(() => {
    let annule = false;
    if (data[cle]) return undefined;
    setBusy(true);
    api(routes[view])
      .then((res) => {
        if (!annule) setData((d) => ({ ...d, [cle]: res }));
      })
      .catch((e) => flash(e.message, "err"))
      .finally(() => {
        if (!annule) setBusy(false);
      });
    // Annulation logique : sans elle, un changement d'onglet rapide écrirait
    // la réponse tardive de la vue qu'on vient de quitter.
    return () => {
      annule = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cle]);

  const courant = data[cle];

  return (
    <div>
      <div className="adm-subnav">
        {ANALYTICS_VIEWS.map((v) => (
          <button
            key={v.key}
            className={"adm-subnav-btn" + (view === v.key ? " on" : "")}
            onClick={() => setView(v.key)}
          >
            {v.label}
          </button>
        ))}
        {view === "overview" && (
          <div className="adm-periods">
            {PERIODS.map((p) => (
              <button
                key={p.days}
                className={"adm-period" + (days === p.days ? " on" : "")}
                onClick={() => setDays(p.days)}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
        {busy && <span className="adm-spin adm-subnav-spin" />}
      </div>

      {!courant && (
        <div className="adm-loading">
          <span className="adm-spin" /> Calcul des indicateurs...
        </div>
      )}
      {courant && view === "overview" && <Overview data={courant} days={days} />}
      {courant && view === "profit" && <Profitability data={courant} />}
      {courant && view === "forecast" && <Forecast data={courant} />}
      {courant && view === "cohorts" && <Cohorts data={courant} />}
      {courant && view === "segments" && <Segments data={courant} />}
      {courant && view === "affinities" && <Affinities data={courant} />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Vue d'ensemble                                                     */
/* ------------------------------------------------------------------ */
/** Colonnes du tableau produits. `get` extrait la valeur, `cell` la formate. */
const PRODUCT_COLUMNS = [
  { key: "name", label: "Produit", get: (p) => p.name },
  { key: "views", label: "Vues", get: (p) => p.views },
  { key: "orders", label: "Commandes", get: (p) => p.orders },
  { key: "units", label: "Unités", get: (p) => p.units },
  { key: "conversion", label: "Conversion", get: (p) => p.conversion },
  { key: "revenue", label: "CA", get: (p) => p.revenue_cents },
  { key: "price", label: "Prix", get: (p) => p.price_cents },
  { key: "rating", label: "Note", get: (p) => p.rating_avg },
  { key: "stock", label: "Stock", get: (p) => p.stock },
];

function Overview({ data, days }) {
  const [sort, setSort] = useState({ col: "revenue", asc: false });

  const k = data.kpis;
  const p = data.period;
  const c = p.current;

  const produits = [...data.products];
  const colonne = PRODUCT_COLUMNS.find((x) => x.key === sort.col) || PRODUCT_COLUMNS[5];
  produits.sort((a, b) => {
    const va = colonne.get(a);
    const vb = colonne.get(b);
    const cmp = typeof va === "string" ? va.localeCompare(vb, "fr") : va - vb;
    return sort.asc ? cmp : -cmp;
  });
  const trier = (key) =>
    setSort((s) => (s.col === key ? { col: key, asc: !s.asc } : { col: key, asc: false }));

  const vus = [...data.products].sort((a, b) => b.views - a.views);
  const commandes = [...data.products].sort((a, b) => b.units - a.units);

  // Indicateurs de la période, chacun comparé à la période précédente de même
  // durée. C'est la comparaison qui porte l'information : un chiffre isolé ne
  // dit pas s'il est bon.
  const periodCards = [
    { label: "Chiffre d'affaires", value: eur(c.revenue_cents), delta: p.change.revenue_cents },
    { label: "Commandes", value: num(c.orders), delta: p.change.orders },
    { label: "Panier moyen", value: eur(c.aov_cents), delta: p.change.aov_cents },
    { label: "Fiches consultées", value: num(c.views), delta: p.change.views },
    { label: "Conversion", value: pct(c.conversion), delta: p.change.conversion },
    { label: "Nouveaux comptes", value: num(c.signups), delta: p.change.signups },
    { label: "Acheteurs", value: num(c.buyers), delta: p.change.buyers },
    {
      label: "Revenu par fiche vue",
      value: eur(c.revenue_per_view_cents),
      delta: p.change.revenue_per_view_cents,
      hint: "Rapproche l'audience du chiffre d'affaires",
    },
  ];

  const cumul = [
    { label: "CA depuis l'origine", value: eur(k.revenue_cents), color: SERIES[2] },
    { label: "Clients", value: num(k.customers), color: SERIES[1] },
    {
      label: "Clients acheteurs",
      value: pct(k.buyer_rate),
      color: SERIES[4],
      hint: `${num(k.buyers)} sur ${num(k.customers)} inscrits`,
    },
    {
      label: "Taux de réachat",
      value: pct(k.repeat_rate),
      color: SERIES[0],
      hint: "Acheteurs revenus au moins une fois",
    },
    {
      label: "Revenu par acheteur",
      value: eur(k.revenue_per_buyer_cents),
      color: SERIES[3],
      hint: "Plancher de la valeur vie client",
    },
  ];

  const serie = data.series;
  // « 2026-07 » devient « 26-07 » : l'axe n'a pas la place d'une année pleine.
  const mois = serie.map((m) => m.month.slice(2));

  return (
    <div>
      <h3 className="adm-sub">
        Sur {days} jours
        <span className="adm-sub-note">
          Comparé aux {days} jours précédents. Une variation absente signale une période antérieure
          vide, donc aucune comparaison possible.
        </span>
      </h3>
      <div className="adm-cards adm-cards-4">
        {periodCards.map((card) => (
          // Le liseré suit le sens de la variation plutôt que de porter une
          // couleur décorative : sur ces huit tuiles, la couleur signifie
          // « ça monte » ou « ça baisse », et une teinte fixe rouge disait le
          // contraire d'un indicateur en hausse. Le libellé chiffré reste à
          // côté — la couleur seule ne porte jamais l'information.
          <div key={card.label} className="adm-card" data-tendance={tendance(card.delta)}>
            <div className="adm-card-top">
              <span className="adm-card-val sm">{card.value}</span>
              <Delta value={card.delta} />
            </div>
            <div className="adm-card-lbl">{card.label}</div>
            {card.hint && <div className="adm-card-hint">{card.hint}</div>}
          </div>
        ))}
      </div>

      <h3 className="adm-sub">Depuis l&apos;origine</h3>
      <div className="adm-cards adm-cards-5">
        {cumul.map((card) => (
          <div key={card.label} className="adm-card" style={{ "--carte-teinte": card.color }}>
            <div className="adm-card-val">{card.value}</div>
            <div className="adm-card-lbl">{card.label}</div>
            {card.hint && <div className="adm-card-hint">{card.hint}</div>}
          </div>
        ))}
      </div>

      <h3 className="adm-sub">Évolution sur 12 mois</h3>
      <div className="viz-grid viz-grid-2">
        {/* Une mesure par graphique. Superposer chiffre d'affaires et audience
            demanderait deux échelles sur un même repère, ce qui fabrique une
            corrélation que les données ne contiennent pas. */}
        <LineChart
          title="Chiffre d'affaires"
          labels={mois}
          format={eur}
          formatTick={axisEuro}
          series={[
            {
              key: "ca",
              label: "Chiffre d'affaires",
              color: SERIES[0],
              values: serie.map((m) => m.revenue_cents),
            },
          ]}
        />
        <LineChart
          title="Commandes"
          labels={mois}
          format={num}
          series={[
            {
              key: "cmd",
              label: "Commandes",
              color: SERIES[1],
              values: serie.map((m) => m.orders),
            },
          ]}
        />
        <LineChart
          title="Audience"
          hint="fiches produit ouvertes"
          labels={mois}
          format={num}
          series={[
            { key: "vues", label: "Vues", color: SERIES[2], values: serie.map((m) => m.views) },
          ]}
        />
        <LineChart
          title="Nouveaux comptes"
          labels={mois}
          format={num}
          series={[
            {
              key: "inscr",
              label: "Inscriptions",
              color: SERIES[3],
              values: serie.map((m) => m.signups),
            },
          ]}
        />
      </div>

      <h3 className="adm-sub">
        Palmarès du catalogue
        <span className="adm-sub-note">
          Toutes les références, classées. Les extrêmes se lisent aux deux bouts sans avoir à
          tronquer la liste : un palmarès de quatre lignes cache ce qui se passe au milieu.
        </span>
      </h3>
      <div className="viz-grid viz-grid-2">
        <BarChart
          title="Audience par référence"
          hint="fiches ouvertes"
          data={vus.map((x) => ({ key: x.name, value: x.views }))}
          format={num}
          color={SERIES[2]}
        />
        <BarChart
          title="Ventes par référence"
          hint="unités écoulées"
          data={commandes.map((x) => ({ key: x.name, value: x.units }))}
          format={num}
          color={SERIES[1]}
        />
      </div>

      <h3 className="adm-sub">
        Détail par référence
        <span className="adm-sub-note">
          Colonnes triables. Un article très vu et peu commandé signale un prix ou une fiche à
          revoir ; l&apos;inverse signale une référence à mettre en avant.
        </span>
      </h3>
      <table className="adm-table">
        <thead>
          <tr>
            {PRODUCT_COLUMNS.map((col) => (
              <th
                key={col.key}
                className={"th-sort" + (sort.col === col.key ? " on" : "")}
                onClick={() => trier(col.key)}
              >
                {col.label}
                {sort.col === col.key ? (sort.asc ? " ↑" : " ↓") : ""}
              </th>
            ))}
            <th>Dernière vente</th>
          </tr>
        </thead>
        <tbody>
          {produits.map((x) => (
            <tr key={x.id} className={x.active ? "" : "adm-row-off"}>
              <td>
                <strong>{x.name}</strong>
                <span className="cell-sub">{x.category}</span>
              </td>
              <td className="mono">{num(x.views)}</td>
              <td className="mono">{num(x.orders)}</td>
              <td className="mono">{num(x.units)}</td>
              <td className="mono">
                <ConversionCell value={x.conversion} />
              </td>
              <td className="mono">{eur(x.revenue_cents)}</td>
              <td className="mono">{eur(x.price_cents)}</td>
              <td className="mono">
                {x.rating_count ? `${x.rating_avg} ★ (${x.rating_count})` : "-"}
              </td>
              <td className="mono">{x.stock}</td>
              <td>
                {x.last_order_at ? (
                  fmtDate(x.last_order_at)
                ) : (
                  <span className="adm-tag off">Jamais</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="viz-grid viz-grid-2 viz-spaced">
        <DonutChart
          title="Chiffre d'affaires par catégorie"
          format={eur}
          total={eur(data.categories.reduce((s, x) => s + x.revenue_cents, 0))}
          data={data.categories.map((x) => ({ key: x.category, value: x.revenue_cents }))}
        />
        <DonutChart
          title="Statut des commandes"
          format={num}
          data={data.statuses.map((s) => ({
            key: STATUS_LABELS[s.status] || s.status,
            value: s.count,
          }))}
        />
      </div>

      <h3 className="adm-sub">Codes promo</h3>
      {data.promos.length === 0 ? (
        <div className="viz-block viz-empty">Aucun code utilisé</div>
      ) : (
        <table className="adm-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Commandes</th>
              <th>CA généré</th>
              <th>Remise consentie</th>
              <th>Panier moyen</th>
            </tr>
          </thead>
          <tbody>
            {data.promos.map((x) => (
              <tr key={x.code}>
                <td className="code">{x.code}</td>
                <td className="mono">{num(x.orders)}</td>
                <td className="mono">{eur(x.revenue_cents)}</td>
                <td className="mono">{eur(x.discount_cents)}</td>
                <td className="mono">{eur(Math.round(x.revenue_cents / x.orders))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 className="adm-sub">Meilleurs clients</h3>
      <table className="adm-table">
        <thead>
          <tr>
            <th>Client</th>
            <th>E-mail</th>
            <th>Ville</th>
            <th>Commandes</th>
            <th>Total dépensé</th>
          </tr>
        </thead>
        <tbody>
          {data.top_customers.map((x) => (
            <tr key={x.id}>
              <td>
                <strong>{x.name}</strong>
              </td>
              <td>{x.email}</td>
              <td>{x.city || "-"}</td>
              <td className="mono">{x.orders}</td>
              <td className="mono">{eur(x.total_cents)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Taux de conversion, colorié par rapport aux repères usuels du commerce en
 *  ligne : sous 2 % on s'inquiète, au-dessus de 10 % on met en avant. */
function ConversionCell({ value }) {
  const tone = value >= 0.1 ? "ok" : value >= 0.05 ? "mid" : "low";
  return <span className={`conv conv-${tone}`}>{pct(value)}</span>;
}

/* ------------------------------------------------------------------ */
/* Rentabilité                                                        */
/* ------------------------------------------------------------------ */
const ABC_HINTS = {
  A: "Les références qui produisent les 80 premiers pour cent de la marge. Jamais en rupture.",
  B: "Les 15 pour cent suivants. Réapprovisionnement normal.",
  C: "Le solde. Candidats à la sortie de catalogue si le stock coûte à porter.",
};

function Profitability({ data }) {
  const p = data.profitability;
  const produits = [...data.products].sort((a, b) => b.margin_cents - a.margin_cents);
  const maxMarge = Math.max(...produits.map((x) => x.margin_cents), 1);
  const c = data.correlation;

  return (
    <div>
      <h3 className="adm-sub">
        Marge brute
        <span className="adm-sub-note">
          Calculée sur le prix et le coût figés dans chaque ligne de commande, pas sur les valeurs
          actuelles de la fiche : un changement de tarif fournisseur ne doit pas réécrire le
          résultat des mois déjà clos.
        </span>
      </h3>
      <div className="adm-cards adm-cards-4">
        <div className="adm-card" style={{ "--carte-teinte": SERIES[2] }}>
          <div className="adm-card-val" style={{ color: SERIES[2] }}>
            {eur(p.margin_cents)}
          </div>
          <div className="adm-card-lbl">Marge dégagée</div>
        </div>
        <div className="adm-card" style={{ "--carte-teinte": SERIES[4] }}>
          <div className="adm-card-val" style={{ color: SERIES[4] }}>
            {pct(p.margin_rate)}
          </div>
          <div className="adm-card-lbl">Taux de marge</div>
          <div className="adm-card-hint">Sur {eur(p.revenue_cents)} de ventes</div>
        </div>
        <div className="adm-card" style={{ "--carte-teinte": SERIES[0] }}>
          <div className="adm-card-val" style={{ color: SERIES[0] }}>
            {p.at_risk.length}
          </div>
          <div className="adm-card-lbl">Ruptures sous 21 jours</div>
          <div className="adm-card-hint">Au rythme des 90 derniers jours</div>
        </div>
        <div className="adm-card" style={{ "--carte-teinte": SERIES[1] }}>
          <div className="adm-card-val" style={{ color: SERIES[1] }}>
            {c.views_units == null ? "—" : c.views_units.toFixed(2)}
          </div>
          <div className="adm-card-lbl">Corrélation vues / ventes</div>
          <div className="adm-card-hint">
            1 = l&apos;audience se transforme, 0 = le frein est ailleurs
          </div>
        </div>
      </div>

      <h3 className="adm-sub">
        Classement ABC
        <span className="adm-sub-note">
          Trié sur la marge et non sur le chiffre d&apos;affaires : c&apos;est elle qui paie les
          charges. Un article à fort volume et faible marge remplit le classement des ventes sans
          rien rapporter.
        </span>
      </h3>
      <div className="abc-grid">
        {p.abc.map((classe) => (
          <div key={classe.classe} className={`abc-card abc-${classe.classe}`}>
            <div className="abc-head">
              <strong>Classe {classe.classe}</strong>
              <span className="mono">{classe.references} réf.</span>
            </div>
            <div className="abc-val mono">{eur(classe.margin_cents)}</div>
            <p className="segment-hint">{ABC_HINTS[classe.classe]}</p>
          </div>
        ))}
      </div>

      <h3 className="adm-sub">Marge par référence</h3>
      <table className="adm-table">
        <thead>
          <tr>
            <th>Produit</th>
            <th>Classe</th>
            <th>Prix</th>
            <th>Coût</th>
            <th>Marge unitaire</th>
            <th>Unités</th>
            <th>Marge totale</th>
            <th>Taux</th>
            <th>Part cumulée</th>
            <th>Stock</th>
          </tr>
        </thead>
        <tbody>
          {produits.map((x) => (
            <tr key={x.id}>
              <td>
                <strong>{x.name}</strong>
                <span className="cell-sub">{x.category}</span>
              </td>
              <td>
                <span className={`abc-tag abc-${x.abc}`}>{x.abc}</span>
              </td>
              <td className="mono">{eur(x.price_cents)}</td>
              <td className="mono">{x.cost_cents ? eur(x.cost_cents) : "—"}</td>
              <td className="mono">{x.cost_cents ? eur(x.unit_margin_cents) : "—"}</td>
              <td className="mono">{num(x.units)}</td>
              <td className="mono">
                <span className="marge-cell">
                  <span className="marge-bar">
                    <span
                      className="marge-fill"
                      style={{ width: `${Math.round((x.margin_cents / maxMarge) * 100)}%` }}
                    />
                  </span>
                  {eur(x.margin_cents)}
                </span>
              </td>
              <td className="mono">{x.margin_rate ? pct(x.margin_rate) : "—"}</td>
              <td className="mono">{pct(x.cumulative_share)}</td>
              <td className="mono">{x.stock}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="adm-sub">
        Ce que le classement par marge change
        <span className="adm-sub-note">
          Les références dont le rang bouge le plus entre les deux classements. Un écart positif
          signale un article qui fait du volume sans rapporter ; un écart négatif, une référence
          discrète qui porte le résultat.
        </span>
      </h3>
      <table className="adm-table">
        <thead>
          <tr>
            <th>Produit</th>
            <th>Rang au CA</th>
            <th>Rang à la marge</th>
            <th>Écart</th>
            <th>Taux de marge</th>
          </tr>
        </thead>
        <tbody>
          {p.rank_shifts.map((r) => (
            <tr key={r.name}>
              <td>
                <strong>{r.name}</strong>
              </td>
              <td className="mono">#{r.revenue_rank}</td>
              <td className="mono">#{r.margin_rank}</td>
              <td className="mono">
                <span
                  className={
                    "delta " +
                    (r.shift > 0 ? "delta-up" : r.shift < 0 ? "delta-down" : "delta-none")
                  }
                >
                  {r.shift > 0 ? `+${r.shift}` : r.shift || "="}
                </span>
              </td>
              <td className="mono">{r.margin_rate ? pct(r.margin_rate) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {p.at_risk.length > 0 && (
        <>
          <h3 className="adm-sub">
            Ruptures à venir
            <span className="adm-sub-note">
              Jours de vente que le stock couvre encore, au rythme des 90 derniers jours.
            </span>
          </h3>
          <table className="adm-table">
            <thead>
              <tr>
                <th>Produit</th>
                <th>Stock</th>
                <th>Ventes par jour</th>
                <th>Couverture</th>
              </tr>
            </thead>
            <tbody>
              {p.at_risk.map((a) => (
                <tr key={a.name}>
                  <td>
                    <strong>{a.name}</strong>
                  </td>
                  <td className="mono">{a.stock}</td>
                  <td className="mono">{a.daily_velocity}</td>
                  <td className="mono">
                    <span className={"conv " + (a.days_of_stock < 7 ? "conv-low" : "conv-mid")}>
                      {a.days_of_stock} j
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tendance et prévision                                              */
/* ------------------------------------------------------------------ */
const MOIS_COURTS = [
  "janv.",
  "févr.",
  "mars",
  "avr.",
  "mai",
  "juin",
  "juil.",
  "août",
  "sept.",
  "oct.",
  "nov.",
  "déc.",
];

function Forecast({ data }) {
  if (!data.trend) {
    return <div className="viz-block viz-empty">Pas encore assez d&apos;historique</div>;
  }

  const t = data.trend;
  // Historique et projection sur la même courbe, la seconde en pointillés pour
  // qu'on ne confonde jamais ce qui a été mesuré avec ce qui est supposé. Le
  // dernier point mesuré porte `charniere` : sans lui, la courbe projetée
  // démarrerait dans le vide au lieu de prolonger la précédente.
  const serie = [
    ...data.history.map((m, i) => ({
      ...m,
      projete: false,
      charniere: i === data.history.length - 1,
    })),
    ...data.projection.map((m) => ({ ...m, projete: true, charniere: false })),
  ];

  return (
    <div>
      <h3 className="adm-sub">
        Tendance du chiffre d&apos;affaires
        <span className="adm-sub-note">
          Droite des moindres carrés sur {data.history.length} mois, prolongée de {data.horizon}{" "}
          mois. Le R² dit quelle part de la variation la droite explique : au-dessous de 0,7, la
          projection ne vaut pas grand-chose.
        </span>
      </h3>

      <div className="adm-cards adm-cards-4">
        <div className="adm-card" style={{ "--carte-teinte": SERIES[2] }}>
          <div className="adm-card-val" style={{ color: SERIES[2] }}>
            {eur(t.slope_cents_per_month)}
          </div>
          <div className="adm-card-lbl">Progression par mois</div>
          <div className="adm-card-hint">
            De {t.from} à {t.to}
          </div>
        </div>
        <div className="adm-card" style={{ "--carte-teinte": SERIES[1] }}>
          <div className="adm-card-val" style={{ color: SERIES[1] }}>
            {t.r2.toFixed(3)}
          </div>
          <div className="adm-card-lbl">Coefficient de détermination</div>
          <div className="adm-card-hint">
            {t.r2 >= 0.9
              ? "Tendance très régulière"
              : t.r2 >= 0.7
                ? "Tendance nette"
                : "Trop irrégulier pour projeter"}
          </div>
        </div>
        <div className="adm-card" style={{ "--carte-teinte": SERIES[4] }}>
          <div className="adm-card-val" style={{ color: SERIES[4] }}>
            {data.cmgr == null ? "—" : pct(data.cmgr)}
          </div>
          <div className="adm-card-lbl">Croissance mensuelle composée</div>
          <div className="adm-card-hint">Lissée sur toute la période</div>
        </div>
        <div className="adm-card" style={{ "--carte-teinte": SERIES[0] }}>
          <div className="adm-card-val" style={{ color: SERIES[0] }}>
            {eur(data.projection[data.projection.length - 1]?.revenue_cents ?? 0)}
          </div>
          <div className="adm-card-lbl">
            Projection {data.projection[data.projection.length - 1]?.month}
          </div>
          <div className="adm-card-hint">Si la tendance se poursuit</div>
        </div>
      </div>

      <div className="viz-grid viz-grid-1">
        {/* Mesuré et projeté sur le même repère, en deux séries distinctes : le
            trait pointillé et la légende disent lequel est une hypothèse. */}
        <LineChart
          title="Chiffre d'affaires mensuel"
          hint="la projection prolonge la droite de tendance"
          height={260}
          labels={serie.map((m) => m.month.slice(2))}
          format={eur}
          formatTick={axisEuro}
          series={[
            {
              key: "mesure",
              label: "Mesuré",
              color: SERIES[0],
              values: serie.map((m) => (m.projete ? null : m.revenue_cents)),
            },
            {
              key: "projete",
              label: "Projeté",
              color: SERIES[4],
              dashed: true,
              values: serie.map((m) => (m.projete || m.charniere ? m.revenue_cents : null)),
            },
          ]}
        />
      </div>

      <h3 className="adm-sub">
        Saisonnalité
        <span className="adm-sub-note">
          Chaque mois calendaire rapporté à la moyenne. Au-dessus de 1, le mois est plus fort que la
          moyenne. Sur douze mois d&apos;historique chaque mois n&apos;est observé qu&apos;une fois
          : l&apos;indice devient fiable au-delà de deux ans.
        </span>
      </h3>
      <BarChart
        title="Indice par mois"
        hint="100 = mois moyen"
        color={SERIES[4]}
        format={(v) => String(v)}
        data={data.seasonality.map((s) => ({
          key: MOIS_COURTS[s.month - 1],
          value: Math.round(s.index * 100),
        }))}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Cohortes                                                           */
/* ------------------------------------------------------------------ */
/** Table de rétention. Une ligne par mois d'inscription, une colonne par mois
 *  écoulé depuis. L'intensité de la couleur porte la valeur : c'est la
 *  diagonale que l'œil doit suivre, pas les chiffres un à un. */
function Cohorts({ data }) {
  const colonnes = data.rows[0]?.cells.length || 0;
  // Échelle calée sur la valeur maximale observée hors mois 0 : celui-ci est
  // toujours le plus fort et écraserait tout le reste du dégradé.
  const max = Math.max(
    ...data.rows.flatMap((r) =>
      r.cells
        .slice(1)
        .filter(Boolean)
        .map((c) => c.rate),
    ),
    0.01,
  );

  return (
    <div>
      <h3 className="adm-sub">
        Rétention par cohorte d&apos;inscription
        <span className="adm-sub-note">
          Chaque ligne suit les comptes créés un même mois. M0 mesure la conversion à
          l&apos;inscription, les colonnes suivantes la fidélisation. Une case vide correspond à un
          mois pas encore advenu pour cette cohorte, ce qui n&apos;est pas la même chose qu&apos;un
          zéro.
        </span>
      </h3>

      <div className="cohort-scroll">
        <table className="cohort-table">
          <thead>
            <tr>
              <th>Cohorte</th>
              <th>Taille</th>
              {Array.from({ length: colonnes }, (_, i) => (
                <th key={i}>M{i}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((ligne) => (
              <tr key={ligne.cohort}>
                <td className="code cohort-key">{ligne.cohort}</td>
                <td className="mono cohort-size">{num(ligne.size)}</td>
                {ligne.cells.map((cell, i) => {
                  if (cell === null) return <td key={i} className="cohort-cell empty" />;
                  return (
                    <td
                      key={i}
                      className="cohort-cell"
                      // Rampe à pas discrets plutôt qu'une opacité continue :
                      // chaque pas est un niveau que la légende traduit, là où
                      // un dégradé ne se lit pas en valeur.
                      style={{ background: heatColor(cell.rate, max) }}
                      title={`${num(cell.active)} client(s) actif(s) sur ${num(ligne.size)}`}
                    >
                      {cell.rate > 0 ? `${(cell.rate * 100).toFixed(1)}` : "–"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <HeatScale max={max} />
      <p className="adm-legend">
        Valeurs en pourcentage de la cohorte. Lecture : sur la ligne d&apos;un mois donné, une
        colonne qui s&apos;assombrit rapidement signale des clients qui ne reviennent pas.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Segmentation RFM                                                   */
/* ------------------------------------------------------------------ */
// Sept segments pour cinq couleurs validées : les deux derniers, marginaux en
// effectif, partagent le gris de repli plutôt que d'inventer deux teintes de
// plus. Au-delà de la palette documentée, une couleur fabriquée redevient
// indistinguable sous daltonisme.
const SEGMENT_COLORS = {
  Champions: SERIES[2],
  Fideles: SERIES[1],
  Prometteurs: SERIES[4],
  Nouveaux: SERIES[3],
  "A risque": SERIES[0],
  "A reactiver": "#7a7166",
  Endormis: "#5a5040",
};

const SEGMENT_HINTS = {
  Champions: "Récents, fréquents, gros paniers. À fidéliser en priorité.",
  Fideles: "Reviennent régulièrement sans être les plus gros acheteurs.",
  Prometteurs: "Achat récent, historique encore mince. À convertir en habitués.",
  Nouveaux: "Une seule commande, récente. Le second achat est l'enjeu.",
  "A risque": "Bons clients qui ne sont pas revenus. La relance a le plus de valeur ici.",
  "A reactiver": "Anciens acheteurs modestes, silencieux depuis longtemps.",
  Endormis: "Une commande ancienne et sans suite. Coût de relance rarement rentable.",
};

function Segments({ data }) {
  if (!data.segments.length) {
    return (
      <div className="viz-block viz-empty">Aucun acheteur à segmenter pour l&apos;instant</div>
    );
  }

  const maxClients = Math.max(...data.segments.map((s) => s.customers));

  return (
    <div>
      <h3 className="adm-sub">
        Segmentation RFM
        <span className="adm-sub-note">
          Chaque acheteur est noté de 1 à 5 sur sa récence, sa fréquence et son montant,
          relativement aux autres clients. Le croisement des trois sépare le client fidèle du client
          unique venu par une promotion, ce qu&apos;aucun total ne montre. {num(data.non_buyers)}{" "}
          inscrits n&apos;ont jamais commandé et sont exclus du calcul.
        </span>
      </h3>

      <div className="segment-grid">
        {data.segments.map((s) => (
          <div key={s.segment} className="segment-card">
            <div className="segment-head">
              <span className="segment-dot" style={{ background: SEGMENT_COLORS[s.segment] }} />
              <strong>{s.segment}</strong>
              <span className="mono segment-count">{num(s.customers)}</span>
            </div>
            <div className="segment-bar">
              <span
                className="segment-fill"
                style={{
                  width: `${Math.round((s.customers / maxClients) * 100)}%`,
                  background: SEGMENT_COLORS[s.segment],
                }}
              />
            </div>
            <div className="segment-stats">
              <span>
                {pct(s.share)} des acheteurs · <strong>{pct(s.revenue_share)} du CA</strong>
              </span>
              <span>
                {eur(s.avg_value_cents)} en moyenne · {s.avg_orders} commande
                {s.avg_orders > 1 ? "s" : ""} · vu il y a {num(s.avg_recency_days)} j
              </span>
            </div>
            <p className="segment-hint">{SEGMENT_HINTS[s.segment]}</p>
          </div>
        ))}
      </div>

      <h3 className="adm-sub">
        Exemples
        <span className="adm-sub-note">
          Les trois plus gros contributeurs de chaque segment. Les scores se lisent RFM : « 555 »
          désigne le meilleur quintile sur les trois axes.
        </span>
      </h3>
      <table className="adm-table">
        <thead>
          <tr>
            <th>Segment</th>
            <th>Client</th>
            <th>Ville</th>
            <th>Scores</th>
            <th>Dernier achat</th>
            <th>Commandes</th>
            <th>Total dépensé</th>
          </tr>
        </thead>
        <tbody>
          {data.examples.map((e) => (
            <tr key={`${e.segment}-${e.email}`}>
              <td>
                <span className="segment-dot" style={{ background: SEGMENT_COLORS[e.segment] }} />
                {e.segment}
              </td>
              <td>
                <strong>{e.name}</strong>
                <span className="cell-sub">{e.email}</span>
              </td>
              <td>{e.city || "-"}</td>
              <td className="code">{e.scores}</td>
              <td className="mono">il y a {num(e.recency_days)} j</td>
              <td className="mono">{e.frequency}</td>
              <td className="mono">{eur(e.monetary_cents)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Analyse de panier                                                  */
/* ------------------------------------------------------------------ */
function Affinities({ data }) {
  if (!data.pairs.length) {
    return (
      <div className="viz-block viz-empty">
        Pas assez de commandes communes pour dégager une règle fiable (seuil :{" "}
        {num(data.min_support_orders)} commandes).
      </div>
    );
  }

  const maxLift = Math.max(...data.pairs.map((p) => p.lift), 1);

  return (
    <div>
      <h3 className="adm-sub">
        Produits achetés ensemble
        <span className="adm-sub-note">
          Calculé sur {num(data.orders)} commandes, avec un seuil de {num(data.min_support_orders)}{" "}
          commandes communes pour écarter les coïncidences. Le <strong>lift</strong> est la mesure
          qui compte : au-dessus de 1, les deux articles s&apos;achètent ensemble plus souvent que
          le hasard ne le voudrait ; en dessous, ils se substituent l&apos;un à l&apos;autre. La
          confiance seule se laisse tromper par les best-sellers, qui se vendent avec tout.
        </span>
      </h3>

      <table className="adm-table">
        <thead>
          <tr>
            <th>Association</th>
            <th>Commandes communes</th>
            <th>Support</th>
            <th>Confiance A→B</th>
            <th>Confiance B→A</th>
            <th>Lift</th>
          </tr>
        </thead>
        <tbody>
          {data.pairs.map((p) => (
            <tr key={`${p.a_id}-${p.b_id}`}>
              <td>
                <strong>{p.a_name}</strong>
                <span className="cell-sub">+ {p.b_name}</span>
              </td>
              <td className="mono">{num(p.orders_together)}</td>
              <td className="mono">{pct(p.support)}</td>
              <td className="mono">{pct(p.confidence_ab)}</td>
              <td className="mono">{pct(p.confidence_ba)}</td>
              <td>
                <div className="lift-cell">
                  <span className="lift-bar">
                    <span
                      className="lift-fill"
                      style={{
                        width: `${Math.round((p.lift / maxLift) * 100)}%`,
                        background: p.lift >= 1 ? SERIES[2] : "#5A5040",
                      }}
                    />
                  </span>
                  <span className={"mono lift-val" + (p.lift >= 1 ? " up" : "")}>
                    ×{p.lift.toFixed(2)}
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="adm-legend">
        Exploitation directe : proposer B sur la fiche de A, composer une offre groupée, ou
        rapprocher les deux références dans le catalogue.
      </p>
    </div>
  );
}

/* ================================================================== */
/* Dashboard                                                          */
/* ================================================================== */
/* Le graphique affiche des libellés lisibles, l'API attend les codes stockés
   en base. La correspondance vit ici, en un seul endroit. */
const CIVILITE_LIBELLES = {
  M: "Homme (M.)",
  F: "Femme (Mme)",
  N: "Non binaire",
  "?": "Non renseigné",
};
const CIVILITE_CLES = Object.fromEntries(
  Object.entries(CIVILITE_LIBELLES).map(([cle, libelle]) => [libelle, cle]),
);

/** Portrait d'achat du segment sélectionné.
 *
 * Toujours affiché, même sans filtre : c'est le portrait de l'ensemble de la
 * clientèle qui donne l'échelle, et sans lui le chiffre d'un segment ne se
 * compare à rien.
 */
function SegmentDetail({ filtre, portrait, onReset }) {
  const criteres = Object.entries(filtre);
  const titre = criteres.length
    ? criteres.map(([dim, val]) => (dim === "civility" ? CIVILITE_LIBELLES[val] : val)).join(" · ")
    : "Toute la clientèle";

  if (!portrait) {
    return (
      <div className="segment-panneau">
        <span className="adm-spin" /> Calcul du segment...
      </div>
    );
  }

  const vide = portrait.customers === 0;

  return (
    <div className={"segment-panneau" + (criteres.length ? " filtre" : "")}>
      <div className="segment-entete">
        <div>
          <span className="ch-title">Portrait d&apos;achat</span>
          <strong className="segment-titre">{titre}</strong>
        </div>
        {criteres.length > 0 && (
          <button className="adm-btn sm" onClick={onReset}>
            ✕ Tout afficher
          </button>
        )}
      </div>

      {vide ? (
        <p className="adm-legend">Aucun client ne correspond à cette combinaison.</p>
      ) : (
        <>
          <div className="segment-chiffres">
            <div>
              <span className="segment-val mono">{num(portrait.customers)}</span>
              <span className="segment-lbl">clients</span>
            </div>
            <div>
              <span className="segment-val mono">{pct(portrait.buyer_rate)}</span>
              <span className="segment-lbl">ont acheté</span>
            </div>
            <div>
              <span className="segment-val mono">{eur(portrait.revenue_cents)}</span>
              <span className="segment-lbl">chiffre d&apos;affaires</span>
            </div>
            <div>
              <span className="segment-val mono">{eur(portrait.aov_cents)}</span>
              <span className="segment-lbl">panier moyen</span>
            </div>
            <div>
              <span className="segment-val mono">{eur(portrait.value_per_customer_cents)}</span>
              <span className="segment-lbl">valeur par client</span>
            </div>
          </div>

          <div className="segment-grille">
            <div className="segment-bloc">
              <span className="ch-title">Ce qu&apos;ils achètent</span>
              <ol className="segment-liste">
                {portrait.top_products.map((p) => (
                  <li key={p.name}>
                    <span className="segment-nom">{p.name}</span>
                    <span className="mono">{num(p.units)} u.</span>
                    <span className="mono segment-second">{eur(p.revenue_cents)}</span>
                  </li>
                ))}
              </ol>
            </div>

            {portrait.best_customer && (
              <div className="segment-bloc">
                <span className="ch-title">Meilleur client</span>
                <strong className="segment-nom-fort">{portrait.best_customer.name}</strong>
                <span className="segment-second">{portrait.best_customer.email}</span>
                <span className="segment-second">
                  {portrait.best_customer.city || "ville non renseignée"} ·{" "}
                  {portrait.best_customer.orders} commandes
                </span>
                <span className="segment-val mono">{eur(portrait.best_customer.total_cents)}</span>
              </div>
            )}

            {portrait.biggest_order && (
              <div className="segment-bloc">
                <span className="ch-title">Plus grosse commande</span>
                <strong className="segment-nom-fort code">{portrait.biggest_order.number}</strong>
                <span className="segment-second">{portrait.biggest_order.email}</span>
                <span className="segment-second">
                  {portrait.biggest_order.created_at
                    ? fmtDate(portrait.biggest_order.created_at)
                    : ""}
                </span>
                <span className="segment-val mono">{eur(portrait.biggest_order.total_cents)}</span>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function Dashboard({ stats }) {
  const d = stats.demographics || {};
  const civ = d.civility || {};
  const ages = d.age_buckets || {};
  const cities = d.top_cities || [];

  const civData = [
    { key: "Homme (M.)", value: civ.M || 0 },
    { key: "Femme (Mme)", value: civ.F || 0 },
    { key: "Non binaire", value: civ.N || 0 },
    ...(civ["?"] ? [{ key: "Non renseigné", value: civ["?"] }] : []),
  ].filter((x) => x.value > 0);

  const ageData = Object.entries(ages)
    .filter(([k, v]) => k !== "?" && v > 0)
    .map(([k, v]) => ({ key: k, value: v }));

  const cityData = cities.map((c) => ({ key: c.city, value: c.count }));

  // Segment en cours d'exploration. Les trois critères se cumulent, et le
  // portrait sans filtre sert de point de comparaison : un chiffre de segment
  // ne veut rien dire seul.
  const [filtre, setFiltre] = useState({});
  const [portrait, setPortrait] = useState(null);

  const choisir = (dimension, valeur) =>
    setFiltre((f) => {
      const suivant = { ...f };
      if (valeur == null) delete suivant[dimension];
      else suivant[dimension] = valeur;
      return suivant;
    });

  useEffect(() => {
    const query = new URLSearchParams(filtre).toString();
    let annule = false;
    api(`/admin/analytics/audience${query ? `?${query}` : ""}`)
      .then((r) => {
        if (!annule) setPortrait(r);
      })
      .catch(() => {
        if (!annule) setPortrait(null);
      });
    return () => {
      annule = true;
    };
  }, [filtre]);

  // `num` plutôt que la valeur brute : « 100 001 » se lit d'un coup d'œil,
  // « 100001 » demande de compter les chiffres.
  const kpis = [
    { label: "Chiffre d'affaires", value: eur(stats.revenue_cents), color: SERIES[2] },
    { label: "Commandes", value: num(stats.order_count), color: SERIES[1] },
    { label: "Clients", value: num(stats.user_count), color: SERIES[4] },
    { label: "Produits actifs", value: num(stats.product_count), color: SERIES[0] },
  ];

  return (
    <div>
      <div className="adm-cards">
        {kpis.map((c) => (
          <div key={c.label} className="adm-card" style={{ "--carte-teinte": c.color }}>
            <div className="adm-card-val">{c.value}</div>
            <div className="adm-card-lbl">{c.label}</div>
          </div>
        ))}
      </div>

      {stats.low_stock_count > 0 && (
        <div className="adm-warn">
          ⚠ {stats.low_stock_count} produit{stats.low_stock_count > 1 ? "s" : ""} avec un stock
          faible (≤ 4)
        </div>
      )}
      {stats.pending_alerts > 0 && (
        <div className="adm-warn adm-info">
          🔔 {stats.pending_alerts} alerte{stats.pending_alerts > 1 ? "s" : ""} de retour en stock
          en attente
        </div>
      )}

      {/* Démographie explorable : un histogramme dit combien ils sont, jamais
          ce qu'ils achètent. Chaque barre ouvre le portrait d'achat du segment,
          et les trois critères se cumulent. */}
      <h3 className="adm-sub">
        Profil clients
        <span className="adm-sub-note">
          Clique une tranche, une ville ou un genre pour voir ce que ce segment achète. Les critères
          se combinent ; un second clic sur le même retire le filtre.
        </span>
      </h3>
      <div className="viz-grid">
        {civData.length > 0 ? (
          <DonutChart
            data={civData}
            title="Répartition par genre"
            format={num}
            selected={filtre.civility && CIVILITE_LIBELLES[filtre.civility]}
            onSelect={(cle) => choisir("civility", cle && CIVILITE_CLES[cle])}
          />
        ) : (
          <div className="viz-block viz-empty">Pas encore de données genre</div>
        )}
        {ageData.length > 0 ? (
          <BarChart
            data={ageData}
            title="Tranches d'âge"
            color={SERIES[1]}
            format={num}
            selected={filtre.age}
            onSelect={(cle) => choisir("age", cle)}
          />
        ) : (
          <div className="viz-block viz-empty">Pas encore de données âge</div>
        )}
        {cityData.length > 0 ? (
          <BarChart
            data={cityData}
            title="Top villes"
            color={SERIES[2]}
            format={num}
            selected={filtre.city}
            onSelect={(cle) => choisir("city", cle)}
          />
        ) : (
          <div className="viz-block viz-empty">Pas encore de données ville</div>
        )}
      </div>

      <SegmentDetail filtre={filtre} portrait={portrait} onReset={() => setFiltre({})} />

      <h3 className="adm-sub">Dernières commandes</h3>
      <table className="adm-table">
        <thead>
          <tr>
            <th>Numéro</th>
            <th>Client</th>
            <th>Montant</th>
            <th>Statut</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {stats.recent_orders.map((o) => (
            <tr key={o.number}>
              <td className="code">{o.number}</td>
              <td>{o.email}</td>
              <td className="mono">{eur(o.total_cents)}</td>
              <td>
                <StatusBadge status={o.status} />
              </td>
              <td>{fmtDate(o.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ================================================================== */
/* Produits                                                           */
/* ================================================================== */
function Products({ items, flash, reload, readonly }) {
  const [editing, setEditing] = useState(null); // null | "new" | product
  const [saving, setSaving] = useState(false);

  const save = async (data) => {
    setSaving(true);
    try {
      if (data.id) {
        await api(`/admin/products/${data.id}`, { method: "PATCH", body: data });
        flash("Produit mis à jour");
      } else {
        await api("/admin/products", { method: "POST", body: data });
        flash("Produit créé");
      }
      setEditing(null);
      reload();
    } catch (e) {
      flash(e.message, "err");
    } finally {
      setSaving(false);
    }
  };

  const del = async (id) => {
    if (!confirm("Supprimer / désactiver ce produit ?")) return;
    try {
      await api(`/admin/products/${id}`, { method: "DELETE" });
      flash("Produit retiré");
      reload();
    } catch (e) {
      flash(e.message, "err");
    }
  };

  if (editing !== null)
    return (
      <ProductForm
        item={editing === "new" ? null : editing}
        onSave={save}
        onCancel={() => setEditing(null)}
        saving={saving}
      />
    );

  return (
    <div>
      <div className="adm-toolbar">
        <button
          className="adm-btn primary"
          disabled={readonly}
          title={readonly ? LECTURE_SEULE : undefined}
          onClick={() => setEditing("new")}
        >
          + Nouveau produit
        </button>
        <span className="adm-count">
          {items.filter((p) => p.active).length} actifs · {items.filter((p) => !p.active).length}{" "}
          inactifs
        </span>
      </div>
      <table className="adm-table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Nom</th>
            <th>Catégorie</th>
            <th>Prix</th>
            <th>Stock</th>
            <th>Statut</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id} className={!p.active ? "adm-row-off" : ""}>
              <td className="code">{p.code}</td>
              <td>
                <strong>{p.name}</strong>
              </td>
              <td>
                <span className="adm-tag">{p.category}</span>
              </td>
              <td className="mono">{eur(p.price_cents)}</td>
              <td>
                <span
                  className={
                    p.stock === 0
                      ? "stock-badge out"
                      : p.stock <= 4
                        ? "stock-badge low"
                        : "stock-badge ok"
                  }
                >
                  {p.stock}
                </span>
              </td>
              <td>
                {p.active ? (
                  <span className="adm-tag ok">Actif</span>
                ) : (
                  <span className="adm-tag off">Inactif</span>
                )}
              </td>
              <td>
                <button
                  className="adm-btn sm"
                  disabled={readonly}
                  title={readonly ? LECTURE_SEULE : undefined}
                  onClick={() => setEditing(p)}
                >
                  Modifier
                </button>
                <button
                  className="adm-btn sm danger"
                  disabled={readonly}
                  title={readonly ? LECTURE_SEULE : undefined}
                  onClick={() => del(p.id)}
                >
                  Retirer
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProductForm({ item, onSave, onCancel, saving }) {
  const [f, setF] = useState({
    id: item?.id,
    code: item?.code || "",
    name: item?.name || "",
    category: item?.category || "Collection",
    blurb: item?.blurb || "",
    price_cents: item?.price_cents ?? 0,
    stock: item?.stock ?? 0,
    is_new: item?.is_new ?? false,
    active: item?.active ?? true,
    featured: item?.featured ?? false,
    featured_order: item?.featured_order ?? 0,
    art: item?.art || "enso,#E0382A,#16140F",
    images: item?.images || [],
  });
  const [imgInput, setImgInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState(null);
  const set = (k) => (e) =>
    setF((s) => ({ ...s, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const setNum = (k) => (e) => setF((s) => ({ ...s, [k]: parseInt(e.target.value) || 0 }));

  const artParts = f.art.split(",");
  const setArtPart = (i, v) => {
    const p = [...artParts];
    p[i] = v;
    setF((s) => ({ ...s, art: p.join(",") }));
  };

  const addImg = () => {
    const v = imgInput.trim();
    if (!v) return;
    setF((s) => ({ ...s, images: [...s.images, v] }));
    setImgInput("");
  };
  const removeImg = (i) => setF((s) => ({ ...s, images: s.images.filter((_, j) => j !== i) }));
  const addArtAsImg = () => setF((s) => ({ ...s, images: [...s.images, s.art] }));

  /* Reorganisation : deplacer une image vers le haut / bas */
  const moveImg = (i, dir) => {
    setF((s) => {
      const arr = [...s.images];
      const j = i + dir;
      if (j < 0 || j >= arr.length) return s;
      [arr[i], arr[j]] = [arr[j], arr[i]];
      return { ...s, images: arr };
    });
  };

  /* Definir une image comme principale : la place en position 0 */
  const setAsMain = (i) => {
    setF((s) => {
      const arr = [...s.images];
      const [picked] = arr.splice(i, 1);
      return { ...s, images: [picked, ...arr] };
    });
  };

  /* Lecture d'un fichier en data URI. */
  const readAsDataUrl = (file) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (ev) => resolve(ev.target.result);
      reader.onerror = () => reject(new Error(`Lecture impossible : ${file.name}`));
      reader.readAsDataURL(file);
    });

  /* Import de photos depuis le disque.
   *
   * Chaque photo est reduite avant d'entrer dans le formulaire. Sans cela, une
   * photo de telephone de plusieurs mega-octets partait telle quelle, encodee en
   * base64 dans le corps JSON - donc un tiers plus lourde encore - et l'API
   * repondait « Requete trop volumineuse ».
   *
   * Le traitement est sequentiel et non parallele : les fichiers doivent entrer
   * dans l'ordre de selection. Avec des rappels concurrents, ils arrivaient dans
   * leur ordre de fin de lecture, et la premiere image de la liste - celle qui
   * devient le visuel principal - pouvait ne pas etre celle choisie en premier.
   */
  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files).filter((file) => file.type.startsWith("image/"));
    /* Remis a zero tout de suite : la valeur de l'input ne survit pas a l'await,
       et cela permet de re-selectionner le meme fichier. */
    e.target.value = "";
    if (!files.length) return;

    setUploadErr(null);
    setUploading(true);
    try {
      const prepared = [];
      for (const file of files) {
        prepared.push(await toGalleryImage(await readAsDataUrl(file)));
      }
      setF((s) => ({ ...s, images: [...s.images, ...prepared] }));
    } catch (error) {
      setUploadErr(error.message);
    } finally {
      setUploading(false);
    }
  };

  /* Détermine si une valeur est une vraie image (URL ou base64) ou un motif SVG */
  const isRealImage = (v) => v && (v.startsWith("http") || v.startsWith("data:"));

  return (
    <div className="adm-form-wrap">
      <div className="adm-form-head">
        <h2>{item ? "Modifier un produit" : "Nouveau produit"}</h2>
        <button className="adm-btn" onClick={onCancel}>
          ← Annuler
        </button>
      </div>
      <div className="adm-form-grid">
        <div className="adm-col">
          <label className="adm-field">
            <span>Code produit *</span>
            <input value={f.code} onChange={set("code")} placeholder="HNB-XXX" />
          </label>
          <label className="adm-field">
            <span>Nom *</span>
            <input value={f.name} onChange={set("name")} />
          </label>
          <label className="adm-field">
            <span>Catégorie</span>
            <select value={f.category} onChange={set("category")}>
              {CATS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="adm-field">
            <span>Description courte *</span>
            <textarea value={f.blurb} onChange={set("blurb")} rows={3} />
          </label>
          <div className="adm-row2">
            <label className="adm-field">
              <span>Prix (en centimes *)</span>
              <input type="number" value={f.price_cents} onChange={setNum("price_cents")} min={0} />
              <small>{eur(f.price_cents)}</small>
            </label>
            <label className="adm-field">
              <span>Stock *</span>
              <input type="number" value={f.stock} onChange={setNum("stock")} min={0} />
            </label>
          </div>
          <div className="adm-checks">
            <label>
              <input type="checkbox" checked={f.is_new} onChange={set("is_new")} /> Badge « Nouveau
              »
            </label>
            <label>
              <input type="checkbox" checked={f.active} onChange={set("active")} /> Produit actif
              (visible)
            </label>
            <label>
              <input type="checkbox" checked={f.featured} onChange={set("featured")} /> ★ Mettre en
              avant (carrousel accueil)
            </label>
          </div>
          {f.featured && (
            <label className="adm-field" style={{ maxWidth: 220 }}>
              <span>Ordre dans le carrousel</span>
              <input
                type="number"
                value={f.featured_order}
                onChange={setNum("featured_order")}
                min={0}
              />
              <small>0 = en premier, puis ordre croissant</small>
            </label>
          )}
        </div>

        <div className="adm-col">
          <div className="adm-field">
            <span>Visuel principal (SVG)</span>
            <div className="art-builder">
              <div className="art-preview">
                <svg
                  viewBox="0 0 200 200"
                  width="100"
                  height="100"
                  style={{ border: "1px solid #333", borderRadius: 8 }}
                >
                  <ArtSvg art={f.art} />
                </svg>
              </div>
              <div className="art-controls">
                <label className="adm-field sm">
                  <span>Forme</span>
                  <select
                    value={artParts[0] || "enso"}
                    onChange={(e) => setArtPart(0, e.target.value)}
                  >
                    {SHAPES.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <label className="adm-field sm">
                  <span>Couleur 1</span>
                  <div className="color-row">
                    <input
                      type="color"
                      value={artParts[1] || SERIES[0]}
                      onChange={(e) => setArtPart(1, e.target.value)}
                    />
                    {PALETTE.map((c) => (
                      <button
                        key={c}
                        type="button"
                        className="color-swatch"
                        style={{ background: c }}
                        onClick={() => setArtPart(1, c)}
                      />
                    ))}
                  </div>
                </label>
                <label className="adm-field sm">
                  <span>Couleur 2</span>
                  <div className="color-row">
                    <input
                      type="color"
                      value={artParts[2] || "#16140F"}
                      onChange={(e) => setArtPart(2, e.target.value)}
                    />
                    {PALETTE.map((c) => (
                      <button
                        key={c}
                        type="button"
                        className="color-swatch"
                        style={{ background: c }}
                        onClick={() => setArtPart(2, c)}
                      />
                    ))}
                  </div>
                </label>
                <button type="button" className="adm-btn sm" onClick={addArtAsImg}>
                  Ajouter comme photo
                </button>
              </div>
            </div>
          </div>

          <div className="adm-field">
            <span>Galerie photos</span>
            <p className="img-hint">
              La première photo est l&apos;image principale affichée sur la boutique. Elle est
              recadrée sur un carré de {MAIN_SIZE}&nbsp;px, centré, pour que toutes les fiches aient
              la même résolution - paysage ou portrait indifféremment. Les autres photos gardent
              leur cadrage.
            </p>
            {/* Zone de dépôt / upload fichier */}
            <label className="img-upload-zone">
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={handleFileUpload}
                style={{ display: "none" }}
              />
              <div className="img-upload-inner">
                {uploading ? (
                  <span className="adm-spin" style={{ width: 20, height: 20 }} />
                ) : (
                  <>
                    <span className="img-upload-icon">📁</span>
                    <span>
                      Clique pour sélectionner des photos
                      <br />
                      <small>JPG, PNG, WebP - plusieurs fichiers possibles</small>
                    </span>
                  </>
                )}
              </div>
            </label>
            {uploadErr && <div className="adm-err">⚠ {uploadErr}</div>}
            {/* Liste des images existantes */}
            <div className="img-list">
              {f.images.map((img, i) => (
                <div key={i} className={"img-item" + (i === 0 ? " is-main" : "")}>
                  {i === 0 && <span className="img-main-badge">★ Principale</span>}
                  {isRealImage(img) ? (
                    <img src={img} alt="" className="img-thumb" />
                  ) : (
                    <svg viewBox="0 0 200 200" width="50" height="50">
                      <ArtSvg art={img} />
                    </svg>
                  )}
                  <span className="mono">
                    {isRealImage(img)
                      ? img.startsWith("data:")
                        ? "Photo uploadée"
                        : img.slice(0, 30) + "…"
                      : img.slice(0, 22) + "…"}
                  </span>
                  <div className="img-actions">
                    <button
                      type="button"
                      className="img-ord"
                      disabled={i === 0}
                      onClick={() => moveImg(i, -1)}
                      title="Monter"
                    >
                      ▲
                    </button>
                    <button
                      type="button"
                      className="img-ord"
                      disabled={i === f.images.length - 1}
                      onClick={() => moveImg(i, 1)}
                      title="Descendre"
                    >
                      ▼
                    </button>
                    {i !== 0 && (
                      <button
                        type="button"
                        className="adm-btn sm"
                        onClick={() => setAsMain(i)}
                        title="Définir comme principale"
                      >
                        ★
                      </button>
                    )}
                    <button
                      type="button"
                      className="adm-btn sm danger"
                      onClick={() => removeImg(i)}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {/* Ajouter via URL ou motif SVG */}
            <div className="img-add-row">
              <input
                value={imgInput}
                onChange={(e) => setImgInput(e.target.value)}
                placeholder="ou colle une URL image / motif SVG"
                onKeyDown={(e) => e.key === "Enter" && addImg()}
              />
              <button type="button" className="adm-btn sm" onClick={addImg}>
                Ajouter
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="adm-form-actions">
        <button
          className="adm-btn primary large"
          onClick={async () => {
            /* La premiere photo de la galerie devient le visuel principal
             * (`art`), celui des cartes, du carrousel et de la banniere.
             *
             * Elle est recadree sur un carre de taille fixe : c'est ce qui
             * garantit que toutes les fiches ont la meme resolution, qu'on ait
             * envoye du paysage ou du portrait, et que la grille reste reguliere.
             * La galerie, elle, garde le cadrage d'origine de chaque photo.
             */
            const main = f.images[0];
            if (!isRealImage(main)) {
              onSave(f);
              return;
            }
            setUploadErr(null);
            try {
              onSave({ ...f, art: await toCanonicalMain(main) });
            } catch (error) {
              setUploadErr(`Visuel principal : ${error.message}`);
            }
          }}
          disabled={saving || uploading}
        >
          {saving ? "Enregistrement…" : item ? "Enregistrer les modifications" : "Créer le produit"}
        </button>
      </div>
    </div>
  );
}

/* Composant SVG inline pour la preview */
function ArtSvg({ art }) {
  const parts = (art || "").split(",");
  const [shape, c1, c2] = parts;
  let body = null;
  if (shape === "enso")
    body = (
      <>
        <circle
          cx="100"
          cy="100"
          r="60"
          fill="none"
          stroke={c1 || SERIES[0]}
          strokeWidth="15"
          strokeLinecap="round"
          strokeDasharray="320 100"
          transform="rotate(40 100 100)"
        />
        <circle cx="150" cy="64" r="8" fill={c2 || "#16140F"} />
      </>
    );
  else if (shape === "wave")
    body = (
      <g fill="none" strokeWidth="5.5">
        {[52, 100, 148].map((y, ri) => (
          <g key={ri} stroke={ri % 2 ? c2 : c1}>
            {[5, 55, 105, 155].map((x) => (
              <g key={x}>
                <path d={`M${x - 26} ${y} A26 26 0 0 1 ${x + 26} ${y}`} />
                <path d={`M${x - 14} ${y} A14 14 0 0 1 ${x + 14} ${y}`} />
              </g>
            ))}
          </g>
        ))}
      </g>
    );
  else if (shape === "fan") {
    const pv = [100, 168];
    const ribs = [-72, -48, -24, 0, 24, 48, 72].map((a) => {
      const r = ((a - 90) * Math.PI) / 180;
      return [pv[0] + 96 * Math.cos(r), pv[1] + 96 * Math.sin(r)];
    });
    body = (
      <g>
        <path
          d={`M${pv[0]} ${pv[1]} L${ribs[0][0]} ${ribs[0][1]} A96 96 0 0 1 ${ribs[6][0]} ${ribs[6][1]} Z`}
          fill={c1}
        />
        {ribs.map((p, i) => (
          <line
            key={i}
            x1={pv[0]}
            y1={pv[1]}
            x2={p[0]}
            y2={p[1]}
            stroke={c2}
            strokeWidth="2.5"
            opacity="0.8"
          />
        ))}
        <circle cx={pv[0]} cy={pv[1]} r="8" fill={c2} />
      </g>
    );
  } else if (shape === "torii")
    body = (
      <g fill={c1}>
        <rect x="30" y="46" width="140" height="15" rx="3" />
        <rect x="44" y="74" width="112" height="11" rx="2" />
        <rect x="58" y="60" width="15" height="100" />
        <rect x="127" y="60" width="15" height="100" />
        <circle cx="100" cy="34" r="8" fill={c2} />
      </g>
    );
  else if (shape === "moon")
    body = (
      <g>
        <circle cx="100" cy="92" r="56" fill={c1} />
        <g fill={c2} opacity="0.55">
          <rect x="30" y="120" width="80" height="11" rx="5.5" />
          <rect x="86" y="140" width="84" height="11" rx="5.5" />
        </g>
      </g>
    );
  else if (shape === "asanoha") {
    const cx = 100,
      cy = 100,
      R = 66;
    const pts = [0, 60, 120, 180, 240, 300].map((a) => [
      cx + R * Math.cos((a * Math.PI) / 180),
      cy + R * Math.sin((a * Math.PI) / 180),
    ]);
    body = (
      <g stroke={c1} strokeWidth="4" fill="none" strokeLinejoin="round">
        <polygon points={pts.map((p) => p.join(",")).join(" ")} />
        {pts.map((p, i) => (
          <line key={i} x1={cx} y1={cy} x2={p[0]} y2={p[1]} />
        ))}
        {pts.map((p, i) => (
          <line
            key={"e" + i}
            x1={p[0]}
            y1={p[1]}
            x2={pts[(i + 2) % 6][0]}
            y2={pts[(i + 2) % 6][1]}
            stroke={c2}
            strokeWidth="2.5"
          />
        ))}
      </g>
    );
  }
  return (
    <>
      <rect width="200" height="200" fill={c2 || "#16140F"} opacity="0.10" />
      {body}
    </>
  );
}

/* ================================================================== */
/* Codes promo                                                        */
/* ================================================================== */
function Promos({ items, flash, reload, readonly }) {
  const [form, setForm] = useState(null);
  const [f, setF] = useState({
    code: "",
    kind: "percent",
    percent: 10,
    amount_cents: 500,
    min_subtotal_cents: 0,
    active: true,
    expires_at: "",
  });
  const set = (k) => (e) =>
    setF((s) => ({ ...s, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const save = async () => {
    try {
      const body = {
        ...f,
        percent: f.kind === "percent" ? parseInt(f.percent) : null,
        amount_cents: f.kind === "fixed" ? parseInt(f.amount_cents) : null,
        min_subtotal_cents: parseInt(f.min_subtotal_cents) || 0,
        expires_at: f.expires_at || null,
      };
      if (form?.id) await api(`/admin/promos/${form.id}`, { method: "PATCH", body });
      else await api("/admin/promos", { method: "POST", body });
      flash(form?.id ? "Code mis à jour" : "Code créé");
      setForm(null);
      reload();
    } catch (e) {
      flash(e.message, "err");
    }
  };

  const del = async (id) => {
    if (!confirm("Supprimer ce code promo ?")) return;
    try {
      await api(`/admin/promos/${id}`, { method: "DELETE" });
      flash("Code supprimé");
      reload();
    } catch (e) {
      flash(e.message, "err");
    }
  };

  const openNew = () => {
    setForm({});
    setF({
      code: "",
      kind: "percent",
      percent: 10,
      amount_cents: 500,
      min_subtotal_cents: 0,
      active: true,
      expires_at: "",
    });
  };
  const openEdit = (p) => {
    setForm(p);
    setF({
      code: p.code,
      kind: p.kind,
      percent: p.percent || 10,
      amount_cents: p.amount_cents || 500,
      min_subtotal_cents: p.min_subtotal_cents || 0,
      active: p.active,
      expires_at: p.expires_at?.slice(0, 10) || "",
    });
  };

  return (
    <div>
      <div className="adm-toolbar">
        <button
          className="adm-btn primary"
          disabled={readonly}
          title={readonly ? LECTURE_SEULE : undefined}
          onClick={openNew}
        >
          + Nouveau code
        </button>
      </div>

      {form !== null && (
        <div className="adm-modal-wrap" onClick={() => setForm(null)}>
          <div className="adm-modal" onClick={(e) => e.stopPropagation()}>
            <h3>{form.id ? "Modifier" : "Nouveau code promo"}</h3>
            <label className="adm-field">
              <span>Code</span>
              <input
                value={f.code}
                onChange={set("code")}
                style={{ textTransform: "uppercase" }}
                disabled={!!form.id}
              />
            </label>
            <label className="adm-field">
              <span>Type</span>
              <select value={f.kind} onChange={set("kind")}>
                <option value="percent">Pourcentage (%)</option>
                <option value="fixed">Montant fixe (€)</option>
                <option value="free_shipping">Port offert</option>
              </select>
            </label>
            {f.kind === "percent" && (
              <label className="adm-field">
                <span>Réduction (%)</span>
                <input
                  type="number"
                  value={f.percent}
                  onChange={set("percent")}
                  min={1}
                  max={100}
                />
              </label>
            )}
            {f.kind === "fixed" && (
              <label className="adm-field">
                <span>Montant (centimes)</span>
                <input
                  type="number"
                  value={f.amount_cents}
                  onChange={set("amount_cents")}
                  min={0}
                />
                <small>{eur(f.amount_cents)}</small>
              </label>
            )}
            <label className="adm-field">
              <span>Minimum de commande (centimes)</span>
              <input
                type="number"
                value={f.min_subtotal_cents}
                onChange={set("min_subtotal_cents")}
                min={0}
              />
              <small>{eur(f.min_subtotal_cents)}</small>
            </label>
            <label className="adm-field">
              <span>Expire le (optionnel)</span>
              <input type="date" value={f.expires_at} onChange={set("expires_at")} />
            </label>
            <label className="adm-check">
              <input type="checkbox" checked={f.active} onChange={set("active")} /> Actif
            </label>
            <div className="adm-modal-actions">
              <button className="adm-btn" onClick={() => setForm(null)}>
                Annuler
              </button>
              <button className="adm-btn primary" onClick={save}>
                {form.id ? "Enregistrer" : "Créer"}
              </button>
            </div>
          </div>
        </div>
      )}

      <table className="adm-table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Type</th>
            <th>Valeur</th>
            <th>Min.</th>
            <th>Expire</th>
            <th>Statut</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p) => (
            <tr key={p.id}>
              <td className="code">{p.code}</td>
              <td>
                {
                  { percent: "Pourcentage", fixed: "Montant fixe", free_shipping: "Port offert" }[
                    p.kind
                  ]
                }
              </td>
              <td className="mono">
                {p.kind === "percent"
                  ? `${p.percent} %`
                  : p.kind === "fixed"
                    ? eur(p.amount_cents)
                    : "-"}
              </td>
              <td className="mono">{p.min_subtotal_cents > 0 ? eur(p.min_subtotal_cents) : "-"}</td>
              <td>{p.expires_at ? fmtDate(p.expires_at) : "Jamais"}</td>
              <td>
                {p.active ? (
                  <span className="adm-tag ok">Actif</span>
                ) : (
                  <span className="adm-tag off">Inactif</span>
                )}
              </td>
              <td>
                <button
                  className="adm-btn sm"
                  disabled={readonly}
                  title={readonly ? LECTURE_SEULE : undefined}
                  onClick={() => openEdit(p)}
                >
                  Modifier
                </button>
                <button
                  className="adm-btn sm danger"
                  disabled={readonly}
                  title={readonly ? LECTURE_SEULE : undefined}
                  onClick={() => del(p.id)}
                >
                  Supprimer
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ================================================================== */
/* Commandes                                                          */
/* ================================================================== */
const STATUS_LABELS = {
  paid: "Payée",
  shipped: "Expédiée",
  delivered: "Livrée",
  cancelled: "Annulée",
  refunded: "Remboursée",
  pending: "En attente",
};
const STATUS_NEXT = {
  paid: ["shipped", "cancelled"],
  shipped: ["delivered", "refunded"],
  delivered: [],
  cancelled: [],
  refunded: [],
  pending: ["paid", "cancelled"],
};

function StatusBadge({ status }) {
  const colors = {
    paid: SERIES[1],
    shipped: SERIES[4],
    delivered: SERIES[2],
    cancelled: "#666",
    refunded: SERIES[0],
    pending: "#888",
  };
  return (
    <span className="status-badge" style={{ background: colors[status] || "#888" }}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function Orders({ items, flash, reload, readonly }) {
  const [search, setSearch] = useState("");
  const filtered = items.filter(
    (o) => !search || o.number.includes(search.toUpperCase()) || o.email.includes(search),
  );

  const changeStatus = async (number, status) => {
    try {
      await api(`/admin/orders/${number}/status?status=${status}`, { method: "PATCH" });
      flash(`Statut → ${STATUS_LABELS[status]}`);
      reload();
    } catch (e) {
      flash(e.message, "err");
    }
  };

  return (
    <div>
      <div className="adm-toolbar">
        <input
          className="adm-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher numéro ou e-mail"
        />
        <span className="adm-count">
          {filtered.length} commande{filtered.length > 1 ? "s" : ""}
        </span>
        <button
          className="adm-btn adm-toolbar-end"
          onClick={async () => {
            try {
              await download("/admin/orders.csv", "hanabi-commandes.csv");
              flash("Export CSV téléchargé");
            } catch (e) {
              flash(e.message, "err");
            }
          }}
          title="Une ligne par article, ouvrable dans un tableur"
        >
          ↓ Exporter en CSV
        </button>
      </div>
      <table className="adm-table">
        <thead>
          <tr>
            <th>Numéro</th>
            <th>Client</th>
            <th>Articles</th>
            <th>Total</th>
            <th>Date</th>
            <th>Statut</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((o) => (
            <tr key={o.number}>
              <td className="code">{o.number}</td>
              <td>{o.email}</td>
              <td className="mono">{o.items?.reduce((s, i) => s + i.qty, 0) || "-"}</td>
              <td className="mono">{eur(o.total_cents)}</td>
              <td>{fmtDate(o.created_at)}</td>
              <td>
                <StatusBadge status={o.status} />
              </td>
              <td>
                {STATUS_NEXT[o.status]?.map((next) => (
                  <button
                    key={next}
                    className="adm-btn sm"
                    disabled={readonly}
                    title={readonly ? LECTURE_SEULE : undefined}
                    onClick={() => changeStatus(o.number, next)}
                  >
                    → {STATUS_LABELS[next]}
                  </button>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ================================================================== */
/* Clients                                                            */
/* ================================================================== */
const USERS_PAGE = 40;

function Users({ items, setItems, alerts, flash, readonly }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  // Recherche et pagination côté serveur. Le filtrage en mémoire de la version
  // précédente supposait que toute la clientèle tenait dans la page : vrai sur
  // une douzaine de comptes de démonstration, faux dès le premier millier.
  const fetchPage = useCallback(
    async (q, p) => {
      try {
        const query = new URLSearchParams({ limit: USERS_PAGE, offset: p * USERS_PAGE });
        if (q.trim()) query.set("q", q.trim());
        setItems(await api(`/admin/users?${query}`));
      } catch (e) {
        flash(e.message, "err");
      }
    },
    [setItems, flash],
  );

  // La saisie est temporisée : une requête par caractère saturerait l'API pour
  // un résultat que personne n'a le temps de lire.
  useEffect(() => {
    const timer = setTimeout(() => fetchPage(search, page), 250);
    return () => clearTimeout(timer);
  }, [search, page, fetchPage]);

  const total = items?.total ?? 0;
  const lignes = items?.items ?? [];
  const pages = Math.max(1, Math.ceil(total / USERS_PAGE));

  const toggleAdmin = async (id, val) => {
    if (!confirm(val ? "Passer ce compte en admin ?" : "Retirer les droits admin ?")) return;
    try {
      await api(`/admin/users/${id}/admin?is_admin=${val}`, { method: "PATCH" });
      flash("Droits mis à jour");
      fetchPage(search, page);
    } catch (e) {
      flash(e.message, "err");
    }
  };

  return (
    <div>
      {alerts.length > 0 && (
        <div className="adm-alerts">
          <h3 className="adm-sub">🔔 Alertes retour en stock ({alerts.length})</h3>
          <table className="adm-table">
            <thead>
              <tr>
                <th>Produit ID</th>
                <th>E-mail</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id}>
                  <td className="mono">#{a.product_id}</td>
                  <td>{a.email}</td>
                  <td>{fmtDate(a.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="adm-toolbar">
        <input
          className="adm-search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          placeholder="Rechercher un nom, un e-mail ou une ville"
        />
        <span className="adm-count">
          {total.toLocaleString("fr-FR")} client{total > 1 ? "s" : ""}
        </span>
        <div className="adm-pager adm-toolbar-end">
          <button className="adm-btn sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
            ← Précédent
          </button>
          <span className="mono">
            {page + 1} / {pages}
          </span>
          <button
            className="adm-btn sm"
            disabled={page + 1 >= pages}
            onClick={() => setPage(page + 1)}
          >
            Suivant →
          </button>
        </div>
      </div>
      <table className="adm-table">
        <thead>
          <tr>
            <th>Nom</th>
            <th>E-mail</th>
            <th>Ville</th>
            <th>Commandes</th>
            <th>CA</th>
            <th>Rôle</th>
            <th>Inscrit</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {lignes.map((u) => (
            <tr key={u.id}>
              <td>
                <strong>
                  {u.civility ? u.civility + ". " : ""}
                  {u.name}
                </strong>
              </td>
              <td>{u.email}</td>
              <td>{u.city || "-"}</td>
              <td className="mono">{u.order_count}</td>
              <td className="mono">{eur(u.total_spent_cents)}</td>
              <td>
                {u.is_admin ? (
                  <span className="adm-tag admin">Admin</span>
                ) : (
                  <span className="adm-tag">Client</span>
                )}
              </td>
              <td>{fmtDate(u.created_at)}</td>
              <td>
                <button
                  className="adm-btn sm"
                  disabled={readonly}
                  title={readonly ? LECTURE_SEULE : undefined}
                  onClick={() => toggleAdmin(u.id, !u.is_admin)}
                >
                  {u.is_admin ? "Retirer admin" : "Rendre admin"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ================================================================== */
/* Entrepôt décisionnel                                               */
/* ================================================================== */
/* Cet onglet ne calcule rien et ne dessine aucun graphique : il affiche le
 * contenu brut des tables d'agrégats construites par dbt, avec la requête qui
 * les a produites. C'est délibéré. Les autres onglets montrent des conclusions ;
 * celui-ci montre la matière, et permet de vérifier que les deux concordent.
 *
 * La différence de fond avec l'onglet analytique tient en une phrase : là-bas,
 * chaque affichage relance des agrégations sur la base transactionnelle ; ici,
 * la lecture est un `SELECT ... LIMIT` sur une table déjà calculée. D'où
 * l'horodatage affiché en permanence — ces chiffres sont ceux de la dernière
 * construction, pas ceux de l'instant. */

const TAILLE_PAGE = 25;
const FORMATS_NUMERIQUES = ["euro", "pourcent", "entier", "decimal", "identifiant"];

/** Formate une cellule selon le type annoncé par l'API.
 *
 * Le tiret cadratin pour une valeur absente n'est pas de la coquetterie : dans
 * ces tables, NULL veut dire « non mesurable » — une couverture de stock
 * infinie, un panier moyen sans commande. Afficher 0 à la place ferait lire un
 * effondrement là où il n'y a rien à mesurer.
 */
function celluleEntrepot(valeur, format) {
  if (valeur === null || valeur === undefined) return "—";
  switch (format) {
    case "euro":
      return eur(valeur);
    case "pourcent":
      return pct(valeur);
    case "entier":
      return num(valeur);
    // Sans séparateur de milliers : un identifiant se recopie dans une requête,
    // il ne se lit pas comme une quantité.
    case "identifiant":
      return String(valeur);
    case "decimal":
      return Number(valeur).toLocaleString("fr-FR", { maximumFractionDigits: 3 });
    case "booleen":
      return valeur ? "oui" : "non";
    case "date":
      return fmtDate(valeur);
    default:
      return String(valeur);
  }
}

/** Bloc de code accompagné de son bouton de copie.
 *
 * Le bloc était auparavant un `pre` nu. Le texte restait sélectionnable, mais
 * rien ne le laissait deviner : afficher une requête sous une invitation à la
 * rejouer, sans le moindre affordance pour l'emporter, c'est une promesse qu'on
 * ne tient pas.
 *
 * `navigator.clipboard` n'est pas toujours disponible — il exige un contexte
 * sécurisé (HTTPS, ou localhost qui compte comme tel) et que le document ait le
 * focus. En cas de refus, on ne se contente pas de s'excuser : on sélectionne
 * le bloc, et il ne reste qu'à presser Ctrl+C. L'échec redevient une étape de
 * plus, pas une impasse.
 */
async function copierTexte(texte, flash, bloc) {
  try {
    await navigator.clipboard.writeText(texte);
    flash("Copié dans le presse-papiers");
  } catch {
    if (!bloc?.current) {
      flash("Copie refusée par le navigateur — sélectionne le texte à la main.", "err");
      return;
    }
    const plage = document.createRange();
    plage.selectNodeContents(bloc.current);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(plage);
    flash("Sélectionné : presse Ctrl+C pour copier.");
  }
}

function BlocCode({ titre, texte, flash }) {
  const bloc = useRef(null);
  const copier = () => copierTexte(texte, flash, bloc);

  return (
    <div className="wh-requete">
      <div className="wh-requete-tete">
        <span>{titre}</span>
        <button className="adm-btn sm" onClick={copier}>
          Copier
        </button>
      </div>
      <pre className="wh-sql" ref={bloc}>
        {texte}
      </pre>
    </div>
  );
}

/** Ancienneté d'une date, en clair.
 *
 * « il y a 3 heures » se lit ; un horodatage ISO demande une soustraction
 * mentale. Or c'est exactement la question qu'on se pose devant un chiffre qui
 * ne bouge pas d'un jour à l'autre.
 */
function anciennete(iso) {
  if (!iso) return "jamais";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 2) return "à l'instant";
  if (minutes < 60) return `il y a ${minutes} min`;
  const heures = Math.round(minutes / 60);
  if (heures < 24) return `il y a ${heures} h`;
  return `il y a ${Math.round(heures / 24)} j`;
}

function Warehouse({ flash }) {
  const [etat, setEtat] = useState(null);
  const [cle, setCle] = useState(null);
  const [vue, setVue] = useState(null);
  const [tri, setTri] = useState(null);
  const [sens, setSens] = useState("desc");
  const [page, setPage] = useState(0);
  const [busy, setBusy] = useState(false);
  const [aide, setAide] = useState(null);
  const [resultatSql, setResultatSql] = useState(null);

  useEffect(() => {
    api("/admin/warehouse")
      .then((res) => {
        setEtat(res);
        const premier = res.marts.find((m) => m.disponible);
        if (premier) setCle(premier.cle);
      })
      .catch((e) => flash(e.message, "err"));
    // Les règles et les exemples de la console ne changent jamais : un seul
    // appel à l'ouverture de l'onglet. Un échec n'est pas bloquant — la console
    // reste utilisable sans son aide.
    api("/admin/warehouse/sql/aide")
      .then(setAide)
      .catch(() => setAide(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Changer de table remet le tri et la pagination à zéro : garder un tri sur
  // une colonne absente de la table suivante n'aurait pas de sens, et le
  // serveur le laisserait tomber sans rien dire.
  useEffect(() => {
    setTri(null);
    setSens("desc");
    setPage(0);
    setResultatSql(null);
  }, [cle]);

  useEffect(() => {
    if (!cle) return undefined;
    let annule = false;
    setBusy(true);
    const params = new URLSearchParams({
      limite: String(TAILLE_PAGE),
      decalage: String(page * TAILLE_PAGE),
      sens,
    });
    if (tri) params.set("tri", tri);
    api(`/admin/warehouse/marts/${cle}?${params}`)
      .then((res) => {
        if (!annule) setVue(res);
      })
      .catch((e) => {
        if (!annule) flash(e.message, "err");
      })
      .finally(() => {
        if (!annule) setBusy(false);
      });
    // Annulation logique : sans elle, un changement rapide de table écrirait la
    // réponse tardive de celle qu'on vient de quitter.
    return () => {
      annule = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cle, tri, sens, page]);

  if (!etat) {
    return (
      <div className="adm-loading">
        <span className="adm-spin" /> Inspection de l&apos;entrepôt...
      </div>
    );
  }

  if (!etat.disponible) {
    return (
      <div className="adm-warn adm-info wh-absent">
        <strong>L&apos;entrepôt n&apos;est pas construit sur cette base.</strong>
        <p>
          {etat.raison === "moteur"
            ? "La base courante n'est pas PostgreSQL. Les modèles de l'entrepôt emploient date_trunc, generate_series et des fonctions de fenêtrage : ils ne se construisent que sur PostgreSQL — un conteneur jetable en local, ou Neon."
            : "Les schémas bronze, silver et gold sont absents de cette base. Ils se créent en une commande."}
        </p>
        <BlocCode titre="À lancer" texte="cd hanabi-dwh && python dwh.py build" flash={flash} />
        <p className="wh-note">
          La construction lit les tables de l&apos;application, n&apos;écrit que dans ses propres
          schémas, et ne modifie jamais rien dans le schéma public.
        </p>
      </div>
    );
  }

  const mart = etat.marts.find((m) => m.cle === cle);
  const pages = Math.max(1, Math.ceil((vue?.total || 0) / TAILLE_PAGE));

  return (
    <div>
      {/* Le graphe des trois couches, avant les données : un tableau d'agrégats
          sans son ascendance est un tableau qu'il faut croire sur parole. */}
      <div className="wh-couches">
        {etat.couches.map((couche) => (
          <div key={couche.cle} className={"wh-couche wh-" + couche.cle}>
            <div className="wh-couche-tete">
              <span className="wh-couche-titre">{couche.titre}</span>
              <span className="wh-couche-compte mono">
                {couche.presents.length}/{couche.modeles.length}
              </span>
            </div>
            <p className="wh-couche-resume">{couche.resume}</p>
            <div className="wh-chips">
              {couche.modeles.map((modele) => {
                const present = couche.presents.includes(modele);
                return (
                  <span
                    key={modele}
                    className={"wh-chip" + (present ? "" : " absent")}
                    title={
                      present
                        ? `${couche.cle}.${modele}`
                        : "Modèle déclaré mais absent de la base : reconstruis l'entrepôt."
                    }
                  >
                    {modele}
                  </span>
                );
              })}
            </div>
            <div className="wh-couche-pied">{couche.materialisation}</div>
          </div>
        ))}
      </div>

      <div className="wh-fraicheur">
        <strong>Construit {anciennete(etat.construit_le)}</strong>
        {etat.construit_le && (
          <span className="mono"> · {new Date(etat.construit_le).toLocaleString("fr-FR")}</span>
        )}
        <span className="wh-note">
          {" "}
          — ces chiffres sont ceux de la dernière construction, pas ceux de l&apos;instant.
        </span>
      </div>

      <div className="adm-subnav wh-subnav">
        {etat.marts.map((m) => (
          <button
            key={m.cle}
            className={"adm-subnav-btn" + (cle === m.cle ? " on" : "")}
            disabled={!m.disponible}
            onClick={() => setCle(m.cle)}
          >
            {m.titre}
            <span className="wh-compte mono">{num(m.lignes)}</span>
          </button>
        ))}
        {busy && <span className="adm-spin adm-subnav-spin" />}
      </div>

      {mart && <p className="wh-question">{mart.question}</p>}

      {vue && vue.cle === cle && (
        <>
          <div className="adm-toolbar">
            <span className="adm-count">
              {num(vue.total)} ligne{vue.total > 1 ? "s" : ""} dans{" "}
              <span className="mono">{vue.table}</span>
            </span>
            <div className="adm-pager adm-toolbar-end">
              <button
                className="adm-btn sm"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                ← Précédent
              </button>
              <span className="mono">
                {page + 1} / {pages}
              </span>
              <button
                className="adm-btn sm"
                disabled={page + 1 >= pages}
                onClick={() => setPage(page + 1)}
              >
                Suivant →
              </button>
            </div>
          </div>

          {/* La requête est modifiable et rejouable. Afficher le SQL sans
              pouvoir y toucher, c'était montrer la porte sans la clé : la
              question qu'on se pose devant un agrégat est presque toujours
              « et si je filtrais autrement ? ». */}
          <ConsoleSql sqlInitial={vue.sql} aide={aide} flash={flash} onResultat={setResultatSql} />

          {/* La table du mart s'efface quand une requête libre a rendu un
              résultat : deux tableaux côte à côte, on ne saurait plus lequel
              répond à quoi. « Réinitialiser » la fait revenir. */}
          {!resultatSql && (
            <>
              <TableEntrepot
                colonnes={vue.colonnes}
                lignes={vue.lignes}
                tri={tri}
                sens={sens}
                onTrier={(nom) => {
                  if (tri === nom) setSens(sens === "desc" ? "asc" : "desc");
                  else {
                    setTri(nom);
                    setSens("desc");
                  }
                  setPage(0);
                }}
              />
              {vue.lignes.length === 0 && (
                <p className="wh-note">
                  Table construite mais vide. C&apos;est un résultat en soi : aucune ligne ne
                  satisfait les critères du modèle.
                </p>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Console SQL                                                        */
/* ------------------------------------------------------------------ */
/* Le bloc de requête devient modifiable. Afficher le SQL d'une table sans
 * pouvoir y toucher, c'était montrer la porte sans la clé : la question qu'on
 * se pose devant un agrégat est presque toujours « et si je filtrais
 * autrement ? ».
 *
 * Les garde-fous sont côté serveur, et ils y restent : transaction en lecture
 * seule, délai d'exécution, examen du plan pour vérifier quelles tables sont
 * réellement lues. Rien ici ne prétend valider quoi que ce soit — un contrôle
 * dans le navigateur n'est pas un contrôle. L'interface se contente d'afficher
 * les règles et de rendre lisible le refus quand il tombe. */

function ConsoleSql({ sqlInitial, aide, flash, onResultat }) {
  const [sql, setSql] = useState(sqlInitial);
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [busy, setBusy] = useState(false);
  const [ouverte, setOuverte] = useState(false);
  const champ = useRef(null);

  // Changer de table remplace la requête de départ, mais seulement tant qu'on
  // n'a rien écrit : écraser une requête en cours de rédaction parce qu'on a
  // cliqué sur un autre onglet serait la pire des surprises.
  const [modifiee, setModifiee] = useState(false);
  useEffect(() => {
    if (!modifiee) setSql(sqlInitial);
  }, [sqlInitial, modifiee]);

  async function executer() {
    setBusy(true);
    setErreur(null);
    try {
      const res = await api("/admin/warehouse/sql", {
        method: "POST",
        body: { sql, limite: 100 },
      });
      setResultat(res);
      onResultat?.(res);
    } catch (e) {
      setErreur(e.message);
      setResultat(null);
      onResultat?.(null);
    } finally {
      setBusy(false);
    }
  }

  // Ctrl+Entrée exécute : c'est le raccourci de tous les clients SQL, et taper
  // Entrée dans une requête sur plusieurs lignes doit rester un retour à la
  // ligne.
  function surTouche(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      executer();
    }
  }

  function reinitialiser() {
    setSql(sqlInitial);
    setModifiee(false);
    setResultat(null);
    setErreur(null);
    onResultat?.(null);
  }

  return (
    <div className="wh-console">
      <div className="wh-requete-tete">
        <span>Requête — modifiable</span>
        <div className="wh-console-actions">
          <button
            className="adm-btn sm"
            onClick={() => setOuverte((o) => !o)}
            aria-expanded={ouverte}
          >
            {ouverte ? "Masquer l'aide" : "Aide et exemples"}
          </button>
          {modifiee && (
            <button className="adm-btn sm" onClick={reinitialiser}>
              Réinitialiser
            </button>
          )}
          <button className="adm-btn sm" onClick={() => copierTexte(sql, flash)}>
            Copier
          </button>
          <button className="adm-btn primary sm" onClick={executer} disabled={busy}>
            {busy ? "…" : "Exécuter"}
          </button>
        </div>
      </div>

      <textarea
        ref={champ}
        className="wh-sql wh-saisie"
        value={sql}
        spellCheck={false}
        rows={Math.min(16, Math.max(5, sql.split("\n").length + 1))}
        onChange={(e) => {
          setSql(e.target.value);
          setModifiee(true);
        }}
        onKeyDown={surTouche}
        aria-label="Requête SQL"
      />

      <div className="wh-console-pied">
        <span>
          <kbd>Ctrl</kbd> + <kbd>Entrée</kbd> pour exécuter
        </span>
        {aide && (
          <span className="wh-note">
            Lecture seule · schémas {aide.schemas.join(", ")} · {aide.delai_max_s} s maximum
          </span>
        )}
      </div>

      {ouverte && aide && (
        <div className="wh-aide">
          <ul className="wh-regles">
            {aide.regles.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <div className="wh-exemples">
            {aide.exemples.map((ex) => (
              <button
                key={ex.titre}
                className="wh-exemple"
                onClick={() => {
                  setSql(ex.sql);
                  setModifiee(true);
                  setErreur(null);
                  champ.current?.focus();
                }}
              >
                {ex.titre}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Le refus est rendu tel que le serveur l'a formulé : il dit toujours
          quoi corriger, et le reformuler ici ne ferait que le diluer. */}
      {erreur && <div className="adm-err wh-erreur">⚠ {erreur}</div>}

      {resultat && (
        <div className="wh-resultat">
          <div className="adm-toolbar">
            <span className="adm-count">
              {num(resultat.total)} ligne{resultat.total > 1 ? "s" : ""}
              {resultat.tronque && " (tronqué)"}
              {resultat.tables_lues.length > 0 && (
                <>
                  {" · "}
                  <span className="mono">{resultat.tables_lues.join(", ")}</span>
                </>
              )}
            </span>
          </div>
          {resultat.lignes.length === 0 ? (
            <p className="wh-note">Aucune ligne ne satisfait cette requête.</p>
          ) : (
            <TableEntrepot colonnes={resultat.colonnes} lignes={resultat.lignes} />
          )}
        </div>
      )}
    </div>
  );
}

/** Rendu tabulaire partagé par la vue d'une table et par la console.
 *
 * Extrait pour que les deux affichent exactement de la même façon : sans quoi
 * une requête modifiée d'un caractère se serait affichée autrement que la
 * requête d'origine, et on aurait douté du résultat plutôt que du rendu.
 */
function TableEntrepot({ colonnes, lignes, tri, sens, onTrier }) {
  return (
    <div className="wh-cadre">
      <table className="adm-table wh-table">
        <thead>
          <tr>
            {colonnes.map((colonne) => {
              const numerique = FORMATS_NUMERIQUES.includes(colonne.format);
              const actif = tri === colonne.nom;
              return (
                <th key={colonne.nom} className={numerique ? "num" : undefined}>
                  {onTrier ? (
                    <button
                      className={"wh-tri" + (actif ? " on" : "")}
                      title={`${colonne.nom} · ${colonne.format}`}
                      onClick={() => onTrier(colonne.nom)}
                    >
                      {colonne.libelle}
                      {actif && <span className="wh-sens">{sens === "desc" ? "↓" : "↑"}</span>}
                    </button>
                  ) : (
                    <span title={`${colonne.nom} · ${colonne.format}`}>{colonne.libelle}</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {lignes.map((ligne, i) => (
            <tr key={i}>
              {ligne.map((valeur, j) => (
                <td
                  key={j}
                  className={FORMATS_NUMERIQUES.includes(colonnes[j].format) ? "num" : undefined}
                >
                  {celluleEntrepot(valeur, colonnes[j].format)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
