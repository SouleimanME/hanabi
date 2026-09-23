/** Client HTTP de l'API Hanabi. */

/** Normalise l'URL de l'API donnee par l'environnement. */
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

/** Tire une cle d'idempotence pour une tentative d'achat. */
export function nouvelleCleIdempotence() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const octets = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(octets);
  else for (let i = 0; i < 16; i++) octets[i] = Math.floor(Math.random() * 256);
  return [...octets].map((o) => o.toString(16).padStart(2, "0")).join("");
}

export function setToken(value) {
  token = value;
  try {
    if (value) localStorage.setItem(TOKEN_KEY, value);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* stockage indisponible : le jeton restera valable le temps de l'onglet */
  }
}

// Noms lisibles des champs, pour les refus de validation du serveur
const CHAMPS = {
  email: "l'e-mail",
  password: "le mot de passe",
  name: "le nom",
  birthdate: "la date de naissance",
  phone: "le téléphone",
  cp: "le code postal",
  prenom: "le prénom",
  nom: "le nom",
  adresse: "l'adresse",
  ville: "la ville",
  code: "le code",
  text: "le texte",
};

/** Message d'un refus de validation (422) : le texte écrit pour l'humain s'il
 *  y en a un, sinon le champ en cause, jamais le jargon anglais de Pydantic. */
export function messageDeValidation(erreurs) {
  const premiere = erreurs?.[0];
  if (!premiere) return null;
  if (typeof premiere.msg === "string" && premiere.msg.startsWith("Value error, ")) {
    return premiere.msg.slice("Value error, ".length);
  }
  const champ = [...(premiere.loc ?? [])].reverse().find((p) => typeof p === "string" && CHAMPS[p]);
  return champ
    ? `Vérifie ${CHAMPS[champ]} : la valeur n'est pas acceptée.`
    : "Une valeur saisie n'est pas acceptée.";
}

/** Effectue un appel a l'API et renvoie le corps JSON.
 * @throws {Error} avec `.status` (code HTTP) ou `.network` (serveur injoignable)
 */
export async function request(path, { method = "GET", body, auth = false, idempotencyKey } = {}) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

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
    const detail = Array.isArray(data.detail) ? messageDeValidation(data.detail) : data.detail;
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
  // Produits reellement achetes avec celui-ci, tires de l'entrepot decisionnel
  affinites: (id, lang) => request(`/products/${id}/affinites?${query({ lang })}`),
  addReview: (id, rating, text, antibot) =>
    request(`/products/${id}/reviews`, {
      method: "POST",
      auth: true,
      body: { rating, text, antibot },
    }),
  // `lang` : le courriel de retour en stock part dans la langue de la page
  notify: (id, email, antibot, lang) =>
    request(`/products/${id}/notify`, { method: "POST", body: { email, antibot, lang } }),
  // Mesure d'audience, alimentée à l'ouverture d'une fiche. Le jeton ne part
  // qu'avec l'accord du visiteur ; sans lui, la vue est comptée sans nom.
  view: (id, rattacher = false) =>
    request(`/products/${id}/view`, { method: "POST", auth: rattacher }),
};

export const Auth = {
  register: (payload) => request("/auth/register", { method: "POST", body: payload }),
  login: (email, password, antibot) =>
    request("/auth/login", { method: "POST", body: { email, password, antibot } }),
  me: () => request("/auth/me", { auth: true }),

  /** Confirme une adresse depuis le lien recu par courriel. */
  verifyEmail: (jeton) => request("/auth/verify-email", { method: "POST", body: { jeton } }),

  /** Renvoie un lien de confirmation au compte connecte. */
  resendVerification: () => request("/auth/resend-verification", { method: "POST", auth: true }),

  /** Demande un lien de reinitialisation. */
  forgotPassword: (email) => request("/auth/forgot-password", { method: "POST", body: { email } }),

  /** Fixe un nouveau mot de passe. Rend un jeton d'acces : on est connecte. */
  resetPassword: (jeton, password) =>
    request("/auth/reset-password", { method: "POST", body: { jeton, password } }),
};

/** Gestion de son propre compte. */
export const Compte = {
  /** Modifie seulement les champs passes. Un champ absent n'est pas touche. */
  majProfil: (champs) => request("/compte/profil", { method: "PATCH", auth: true, body: champs }),

  changerMotDePasse: (ancien, nouveau) =>
    request("/compte/mot-de-passe", { method: "POST", auth: true, body: { ancien, nouveau } }),

  changerEmail: (email, password) =>
    request("/compte/email", { method: "POST", auth: true, body: { email, password } }),

  paiements: () => request("/compte/paiements", { auth: true }),

  /** Enregistre une carte. */
  ajouterPaiement: (carte) =>
    request("/compte/paiements", { method: "POST", auth: true, body: carte }),

  paiementParDefaut: (id) =>
    request(`/compte/paiements/${id}/defaut`, { method: "POST", auth: true }),

  supprimerPaiement: (id) => request(`/compte/paiements/${id}`, { method: "DELETE", auth: true }),

  /** Toutes les données détenues sur le compte (RGPD art. 20). */
  exporterMesDonnees: (password) =>
    request("/compte/export", { method: "POST", auth: true, body: { password } }),

  /** Efface le compte (RGPD art. 17). */
  supprimerMonCompte: (password, confirmation) =>
    request("/compte/suppression", {
      method: "POST",
      auth: true,
      body: { password, confirmation },
    }),
};

export const Orders = {
  quote: (items, promoCode) =>
    request("/orders/quote", { method: "POST", body: { items, promo_code: promoCode || null } }),
  /** Passe la commande.
   * @param {object} payload corps de la commande
   * @param {string} cle identifiant stable de cette tentative d'achat
   */
  checkout: (payload, cle) =>
    request("/orders/checkout", {
      method: "POST",
      auth: true,
      body: payload,
      idempotencyKey: cle,
    }),
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

  /** Désinscription depuis le lien signé du courriel ; rend `{ ok, deja, email }`,
   *  l'adresse masquée. */
  unsubscribe: (id, signature) =>
    request("/newsletter/unsubscribe", { method: "POST", body: { id, signature } }),
};
