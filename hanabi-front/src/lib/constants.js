/** Regles commerciales partagees par l'interface.
 *
 * Attention : ces valeurs servent uniquement a l'affichage optimiste
 * (estimation du panier avant la reponse du serveur). Le montant qui fait
 * foi est toujours celui renvoye par `POST /orders/quote`, calcule cote
 * backend dans `app/pricing.py`. Toute divergence doit etre corrigee la-bas.
 */

/** Frais de port appliques sous le seuil de gratuite, en centimes. */
export const SHIPPING_CENTS = 690;

/** Montant du panier a partir duquel le port est offert, en centimes. */
export const FREE_SHIPPING_CENTS = 8000;

/** Categories du catalogue. "Tout" est un filtre, pas une categorie en base. */
export const CATEGORIES = ["Tout", "Compagnons", "Tradition", "Collection"];
