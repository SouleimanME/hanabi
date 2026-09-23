/** Correspondance entre l'etat d'affichage et l'URL. */

/** Segment d'URL pour chaque ecran. `home` vit a la racine. */
const SEGMENTS = {
  wishlist: "favoris",
  saved: "enregistres",
  account: "compte",
  checkout: "commande",
  done: "merci",
  // Ecrans atteints depuis un courriel, jamais par la navigation
  verifyEmail: "confirmer-adresse",
  resetPassword: "nouveau-mot-de-passe",
  unsubscribe: "desinscription",
};

/** Ecrans qui attendent un jeton dans la requete. */
const AVEC_JETON = new Set(["verifyEmail", "resetPassword"]);

/** Longueur maximale acceptee pour un jeton lu dans l'URL. */
const LONGUEUR_MAX_JETON = 128;

const VIEW_BY_SEGMENT = Object.fromEntries(
  Object.entries(SEGMENTS).map(([view, segment]) => [segment, view]),
);

const PRODUCT_SEGMENT = "produit";

/** URL correspondant a un etat d'affichage.
 * @param {string} view
 * @param {{id: number}|null} [product] fiche ouverte, pour l'ecran produit
 * @returns {string}
 */
export function pathFor(view, product) {
  if (view === "product") {
    return product ? `/${PRODUCT_SEGMENT}/${product.id}` : "/";
  }
  const segment = SEGMENTS[view];
  return segment ? `/${segment}` : "/";
}

/** Etat d'affichage decrit par une URL.
 * @param {string} pathname
 * @param {string} [search] chaine de requete, pour les ecrans a jeton
 * @returns {{view: string, productId: number|null, jeton: string|null,
 *   lien: {id: number, signature: string}|null}}
 */
export function parsePath(pathname, search = "") {
  const parts = pathname.split("/").filter(Boolean);
  const accueil = { view: "home", productId: null, jeton: null, lien: null };

  if (parts[0] === PRODUCT_SEGMENT) {
    const id = Number(parts[1]);
    return Number.isInteger(id) && id > 0
      ? { view: "product", productId: id, jeton: null, lien: null }
      : accueil;
  }

  const view = VIEW_BY_SEGMENT[parts[0]] ?? "home";

  // Un ecran a jeton sans jeton retombe sur l'accueil
  if (AVEC_JETON.has(view)) {
    const jeton = lireJeton(search);
    return jeton ? { view, productId: null, jeton, lien: null } : accueil;
  }

  // Lien de desinscription : adresse et signature, verifiees par le serveur
  if (view === "unsubscribe") {
    const lien = lireLienDesinscription(search);
    return lien ? { view, productId: null, jeton: null, lien } : accueil;
  }

  return { view, productId: null, jeton: null, lien: null };
}

/** Numero d'inscription et signature d'un lien de desinscription, ou null si la
 *  forme ne va pas. Le lien ne porte pas l'adresse e-mail. */
function lireLienDesinscription(search) {
  let params;
  try {
    params = new URLSearchParams(search);
  } catch {
    return null;
  }
  const id = Number(params.get("i"));
  const signature = (params.get("s") || "").trim();
  if (!Number.isInteger(id) || id < 1) return null;
  if (!/^[0-9a-f]{64}$/.test(signature)) return null;
  return { id, signature };
}

/** Extrait et valide le jeton d'une chaine de requete. */
function lireJeton(search) {
  let brut;
  try {
    brut = new URLSearchParams(search).get("jeton");
  } catch {
    return null;
  }
  if (!brut) return null;

  const propre = brut.trim();
  // Le serveur emet du base64url : lettres, chiffres, tiret, tiret bas
  if (propre.length < 16 || propre.length > LONGUEUR_MAX_JETON) return null;
  if (!/^[\w-]+$/.test(propre)) return null;
  return propre;
}
