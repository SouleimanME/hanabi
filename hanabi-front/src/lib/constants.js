/** Regles commerciales partagees par l'interface. */

/** Frais de port appliques sous le seuil de gratuite, en centimes. */
export const SHIPPING_CENTS = 690;

/** Montant du panier a partir duquel le port est offert, en centimes. */
export const FREE_SHIPPING_CENTS = 8000;

/** Categories du catalogue. "Tout" est un filtre, pas une categorie en base.
 *  "Accessoires" existe au back-office ; l'ajouter ici, et au pied de page,
 *  quand le premier accessoire est en ligne : un filtre vide ferait défaut. */
export const CATEGORIES = ["Tout", "Figurines", "Décoration", "Luminaires"];
