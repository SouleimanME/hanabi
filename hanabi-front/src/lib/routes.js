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
};

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
 * @returns {{view: string, productId: number|null}}
 */
export function parsePath(pathname) {
  const parts = pathname.split("/").filter(Boolean);

  if (parts[0] === PRODUCT_SEGMENT) {
    const id = Number(parts[1]);
    return Number.isInteger(id) && id > 0
      ? { view: "product", productId: id }
      : { view: "home", productId: null };
  }

  return { view: VIEW_BY_SEGMENT[parts[0]] ?? "home", productId: null };
}
