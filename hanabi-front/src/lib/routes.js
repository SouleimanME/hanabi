/** Correspondance entre l'etat d'affichage et l'URL.
 *
 * La boutique pilotait sa navigation par un simple etat React, sans URL. Le
 * commentaire d'en-tete de App.jsx assumait la limite : le bouton Retour du
 * navigateur ne parcourait pas les ecrans, et aucune fiche produit n'etait
 * partageable ni memorisable dans les favoris.
 *
 * On corrige avec l'API History du navigateur plutot qu'avec react-router : le
 * besoin tient en une table de quelques entrees, et le projet a fait le choix
 * explicite de ne pas ajouter cette dependance.
 *
 * Les segments sont en francais parce qu'ils sont visibles par le visiteur.
 * Ils sont volontairement stables : une URL partagee doit continuer de
 * fonctionner, meme si le nom interne de l'ecran change.
 */

/** Segment d'URL pour chaque ecran. `home` vit a la racine. */
const SEGMENTS = {
  wishlist: "favoris",
  saved: "enregistres",
  account: "compte",
  checkout: "commande",
  done: "merci",
  // Deux ecrans atteints depuis un COURRIEL, jamais par la navigation. Leurs
  // segments sont donc encore plus figes que les autres : ils vivent dans des
  // messages deja partis, que personne ne peut corriger apres coup. Les
  // renommer casserait tous les liens en circulation.
  verifyEmail: "confirmer-adresse",
  resetPassword: "nouveau-mot-de-passe",
};

/** Ecrans qui attendent un jeton dans la requete. */
const AVEC_JETON = new Set(["verifyEmail", "resetPassword"]);

/** Longueur maximale acceptee pour un jeton lu dans l'URL.
 *
 * Le serveur emet 32 octets en base64url, soit 43 caracteres. La borne evite
 * qu'une adresse forgee ne fasse transiter une charge demesuree jusqu'a l'API. */
const LONGUEUR_MAX_JETON = 128;

const VIEW_BY_SEGMENT = Object.fromEntries(
  Object.entries(SEGMENTS).map(([view, segment]) => [segment, view]),
);

const PRODUCT_SEGMENT = "produit";

/**
 * URL correspondant a un etat d'affichage.
 *
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

/**
 * Etat d'affichage decrit par une URL.
 *
 * Toute URL inconnue retombe sur l'accueil : une adresse erronee ou un ancien
 * lien ne doit pas produire d'ecran vide.
 *
 * @param {string} pathname
 * @param {string} [search] chaine de requete, pour les ecrans a jeton
 * @returns {{view: string, productId: number|null, jeton: string|null}}
 */
export function parsePath(pathname, search = "") {
  const parts = pathname.split("/").filter(Boolean);

  if (parts[0] === PRODUCT_SEGMENT) {
    const id = Number(parts[1]);
    return Number.isInteger(id) && id > 0
      ? { view: "product", productId: id, jeton: null }
      : { view: "home", productId: null, jeton: null };
  }

  const view = VIEW_BY_SEGMENT[parts[0]] ?? "home";

  // Un ecran a jeton SANS jeton retombe sur l'accueil. C'est l'adresse tapee a
  // la main ou le lien tronque par un client de messagerie : mieux vaut la page
  // d'accueil qu'un formulaire qui ne peut rien valider et dont l'echec ne
  // s'expliquerait pas.
  if (AVEC_JETON.has(view)) {
    const jeton = lireJeton(search);
    return jeton
      ? { view, productId: null, jeton }
      : { view: "home", productId: null, jeton: null };
  }

  return { view, productId: null, jeton: null };
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
  // Le serveur emet du base64url : lettres, chiffres, tiret, tiret bas. Tout
  // autre caractere signale une adresse forgee ou abimee, et rien ne sert de la
  // transmettre a l'API pour s'entendre repondre non.
  if (propre.length < 16 || propre.length > LONGUEUR_MAX_JETON) return null;
  if (!/^[\w-]+$/.test(propre)) return null;
  return propre;
}
