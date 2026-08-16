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

/** Tire une cle d'idempotence pour une tentative d'achat.
 *
 * `randomUUID` n'existe que sur les origines sures - HTTPS, ou localhost. Le
 * repli n'est pas un detail : sans lui, la fonction leverait sur un site servi
 * en HTTP, et la commande echouerait au lieu de simplement perdre sa protection
 * contre le double envoi.
 */
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

/**
 * Effectue un appel a l'API et renvoie le corps JSON.
 *
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

  /** Confirme une adresse depuis le lien recu par courriel. */
  verifyEmail: (jeton) => request("/auth/verify-email", { method: "POST", body: { jeton } }),

  /** Renvoie un lien de confirmation au compte connecte. */
  resendVerification: () => request("/auth/resend-verification", { method: "POST", auth: true }),

  /**
   * Demande un lien de reinitialisation.
   *
   * Repond toujours succes, compte connu ou non : c'est ce qui empeche ce
   * formulaire de servir a tester une liste d'adresses. L'interface doit donc
   * afficher le meme message dans les deux cas, sans quoi elle reintroduirait
   * cote client la fuite que le serveur refuse.
   */
  forgotPassword: (email) => request("/auth/forgot-password", { method: "POST", body: { email } }),

  /** Fixe un nouveau mot de passe. Rend un jeton d'acces : on est connecte. */
  resetPassword: (jeton, password) =>
    request("/auth/reset-password", { method: "POST", body: { jeton, password } }),
};

/** Gestion de son propre compte.
 *
 * Toutes ces routes agissent sur le porteur du jeton : aucune ne prend
 * d'identifiant de compte, donc aucune ne se detourne vers celui d'un autre.
 */
export const Compte = {
  /** Modifie SEULEMENT les champs passes. Un champ absent n'est pas touche. */
  majProfil: (champs) => request("/compte/profil", { method: "PATCH", auth: true, body: champs }),

  changerMotDePasse: (ancien, nouveau) =>
    request("/compte/mot-de-passe", { method: "POST", auth: true, body: { ancien, nouveau } }),

  changerEmail: (email, password) =>
    request("/compte/email", { method: "POST", auth: true, body: { email, password } }),

  paiements: () => request("/compte/paiements", { auth: true }),

  /**
   * Enregistre une carte.
   *
   * `carte` ne contient NI numero NI cryptogramme : le navigateur en tire de
   * quoi reconnaitre la carte a l'ecran, et rien d'autre ne part. C'est le
   * partage des roles d'une integration reelle, ou le numero ne quitte jamais
   * l'iframe du prestataire.
   */
  ajouterPaiement: (carte) =>
    request("/compte/paiements", { method: "POST", auth: true, body: carte }),

  paiementParDefaut: (id) =>
    request(`/compte/paiements/${id}/defaut`, { method: "POST", auth: true }),

  supprimerPaiement: (id) => request(`/compte/paiements/${id}`, { method: "DELETE", auth: true }),

  /** Toutes les données détenues sur le compte (RGPD art. 20). */
  exporterMesDonnees: (password) =>
    request("/compte/export", { method: "POST", auth: true, body: { password } }),

  /**
   * Efface le compte (RGPD art. 17). IRRÉVERSIBLE.
   *
   * Deux confirmations, exigées par le serveur : le mot de passe prouve qu'on
   * est bien là maintenant, la formule recopiée prouve qu'on a lu ce qui va se
   * passer.
   */
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
  /**
   * Passe la commande. La cle d'idempotence est TIREE PAR L'APPELANT, et c'est
   * la seule facon dont le mecanisme fonctionne : une cle generee ici serait
   * neuve a chaque appel, donc chaque reessai creerait une commande. Elle doit
   * etre tiree une fois a l'ouverture du tunnel et repetee a l'identique tant
   * que le meme achat est en cours.
   *
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
};
