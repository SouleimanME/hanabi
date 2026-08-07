/** Client HTTP de l'API Hanabi.
 *
 * Un seul point de passage pour tous les appels reseau : la gestion du jeton,
 * des erreurs et de l'URL de base est faite ici, et nulle part ailleurs.
 *
 * Le jeton vit en memoire et est replique dans le localStorage pour survivre
 * a un rechargement. En production reelle, un cookie httpOnly serait plus sur
 * (inaccessible au JavaScript, donc insensible au vol par XSS) ; le choix du
 * localStorage est assume ici pour garder un backend sans etat de session.
 */

/** Normalise l'URL de l'API donnee par l'environnement.
 *
 * Deux erreurs de configuration classiques, qui echouent silencieusement une
 * fois le site en ligne :
 *   - l'URL collee depuis un tableau de bord d'hebergeur arrive souvent sans
 *     protocole (« mon-api.onrender.com »), ce qui produit une requete relative
 *     vers un chemin inexistant ;
 *   - une barre oblique finale produit des URL a double barre avant le chemin,
 *     que certains serveurs refusent.
 *
 * On corrige les deux ici, une fois, plutot que de compter sur une saisie
 * parfaite. En developpement l'URL locale reste en http.
 */
function normaliseBase(raw) {
  const value = (raw || "").trim();
  if (!value) return "http://localhost:8000";
  const withScheme = /^https?:\/\//i.test(value) ? value : `https://${value}`;
  return withScheme.replace(/\/+$/, "");
}

/** Racine de l'API, normalisee. Exportee pour que le back-office s'en serve
 *  aussi : il appelle l'API avec son propre client et dupliquait ce calcul. */
export const API_BASE = normaliseBase(import.meta.env.VITE_API_URL);

const BASE = API_BASE;
const TOKEN_KEY = "hanabi:token";

let token = null;
try {
  token = localStorage.getItem(TOKEN_KEY);
} catch {
  /* stockage indisponible : on reste en memoire seule */
}

export const getToken = () => token;

export function setToken(value) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* stockage indisponible : le jeton restera valable le temps de l'onglet */
  }
}

/**
 * Effectue un appel a l'API et renvoie le corps JSON.
 *
 * @throws {Error} avec `.status` (code HTTP) ou `.network` (serveur injoignable)
 */
export async function request(path, { method = "GET", body, auth = false } = {}) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch ne rejette que sur une panne reseau, jamais sur un code 4xx/5xx.
    const err = new Error(`Serveur injoignable. Le backend tourne-t-il sur ${BASE} ?`);
    err.network = true;
    throw err;
  }

  if (res.status === 204) return null;

  let data = {};
  try {
    data = await res.json();
  } catch {
    /* reponse sans corps JSON : on garde un objet vide */
  }

  if (!res.ok) {
    // FastAPI renvoie soit une chaine, soit la liste d'erreurs de validation
    // Pydantic. On extrait le premier message lisible dans les deux cas.
    const detail = Array.isArray(data.detail) ? data.detail[0]?.msg : data.detail;
    const err = new Error(detail || `Erreur ${res.status}`);
    err.status = res.status;
    throw err;
  }

  return data;
}

/** Construit une query string en ignorant les valeurs vides. */
function query(params) {
  const clean = Object.entries(params).filter(([, v]) => v != null && v !== "");
  return new URLSearchParams(Object.fromEntries(clean)).toString();
}

// Les formulaires publics joignent un bloc `antibot` (defi resolu, pot de miel,
// horodatage signe). Il est produit par useAntiBot et passe tel quel.
export const Products = {
  list: (params = {}) => request(`/products?${query(params)}`),
  get: (id, lang) => request(`/products/${id}?${query({ lang })}`),
  featured: (lang) => request(`/products/featured?${query({ lang })}`),
  reviews: (id) => request(`/products/${id}/reviews`),
  // Produits reellement achetes avec celui-ci, tires de l'entrepot decisionnel.
  // Rend une liste vide si l'entrepot n'est pas construit : l'appelant n'affiche
  // alors simplement rien.
  affinites: (id, lang) => request(`/products/${id}/affinites?${query({ lang })}`),
  addReview: (id, rating, text, antibot) =>
    request(`/products/${id}/reviews`, {
      method: "POST",
      auth: true,
      body: { rating, text, antibot },
    }),
  notify: (id, email, antibot) =>
    request(`/products/${id}/notify`, { method: "POST", body: { email, antibot } }),
  // Mesure d'audience, alimentee a l'ouverture d'une fiche. `auth: true` pour
  // rattacher la vue au compte quand il y en a un ; sinon la ligne enregistree
  // est anonyme. Les erreurs sont avalees par l'appelant : une mesure ratee ne
  // doit jamais gener la consultation du produit.
  view: (id) => request(`/products/${id}/view`, { method: "POST", auth: true }),
};

export const Auth = {
  register: (payload) => request("/auth/register", { method: "POST", body: payload }),
  login: (email, password, antibot) =>
    request("/auth/login", { method: "POST", body: { email, password, antibot } }),
  me: () => request("/auth/me", { auth: true }),
};

export const Orders = {
  quote: (items, promoCode) =>
    request("/orders/quote", { method: "POST", body: { items, promo_code: promoCode || null } }),
  checkout: (payload) => request("/orders/checkout", { method: "POST", auth: true, body: payload }),
  history: () => request("/orders", { auth: true }),
};

export const Promos = {
  validate: (code, subtotalCents) =>
    request("/promos/validate", { method: "POST", body: { code, subtotal_cents: subtotalCents } }),
};

export const Newsletter = {
  /** Inscrit une adresse et renvoie `{ ok, code }`, `code` etant l'offre de
   *  bienvenue si elle est active en base. */
  subscribe: (email, lang, antibot) =>
    request("/newsletter/subscribe", { method: "POST", body: { email, lang, antibot } }),
};
