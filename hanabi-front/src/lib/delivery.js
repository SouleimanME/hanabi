/** Estimation de la date de livraison.
 *
 * Un delai (« expedie sous 48 h ») laisse le calcul a la charge du visiteur, qui
 * doit deviner si les week-ends comptent. Une date (« chez toi mardi 4 aout »)
 * repond directement a la seule question qu'il se pose : est-ce que ce sera la
 * a temps.
 *
 * L'estimation reste volontairement prudente et n'est jamais presentee comme un
 * engagement : annoncer une date qu'on ne tient pas coute plus cher que de ne
 * rien annoncer.
 */

/** Heure limite, au-dela de laquelle la preparation commence le lendemain. */
export const CUTOFF_HOUR = 15;

/** Jours ouvres de transport, une fois le colis remis au transporteur. */
const TRANSIT_DAYS = 2;

const SATURDAY = 6;
const SUNDAY = 0;

/** Ajoute un nombre de jours ouvres, en sautant samedi et dimanche.
 *
 * Les jours feries ne sont pas geres : ils dependent du pays de livraison, et
 * une table de dates en dur vieillirait mal. La marge de transport les absorbe
 * dans la plupart des cas.
 */
function addBusinessDays(from, days) {
  const date = new Date(from);
  let left = days;
  while (left > 0) {
    date.setDate(date.getDate() + 1);
    const day = date.getDay();
    if (day !== SATURDAY && day !== SUNDAY) left -= 1;
  }
  return date;
}

/** `true` si une commande passee maintenant part encore aujourd'hui. */
export function isBeforeCutoff(from = new Date()) {
  const day = from.getDay();
  if (day === SATURDAY || day === SUNDAY) return false;
  return from.getHours() < CUTOFF_HOUR;
}

/**
 * Date de livraison estimee pour une commande passee maintenant.
 *
 * @param {Date} [from]
 * @returns {Date}
 */
export function estimateDelivery(from = new Date()) {
  const prepDays = isBeforeCutoff(from) ? 1 : 2;
  return addBusinessDays(from, prepDays + TRANSIT_DAYS);
}

/**
 * Date lisible dans la langue affichee : « mardi 4 aout ».
 *
 * L'annee est omise : une estimation a quatre jours ne franchit un changement
 * d'annee qu'une fois sur cent, et la porter alourdirait la phrase.
 *
 * @param {Date} date
 * @param {string} lang
 * @returns {string}
 */
export function formatDeliveryDate(date, lang) {
  return new Intl.DateTimeFormat(lang, {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
}
