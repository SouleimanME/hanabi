/** Estimation de la date de livraison. */

/** Heure limite, au-dela de laquelle la preparation commence le lendemain. */
export const CUTOFF_HOUR = 15;

/** Jours ouvres de transport, une fois le colis remis au transporteur. */
const TRANSIT_DAYS = 2;

const SATURDAY = 6;
const SUNDAY = 0;

/** Ajoute un nombre de jours ouvres, en sautant samedi et dimanche. */
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

/** Date de livraison estimee pour une commande passee maintenant.
 * @param {Date} [from]
 * @returns {Date} minuit, le jour de livraison estime
 */
export function estimateDelivery(from = new Date()) {
  const prepDays = isBeforeCutoff(from) ? 1 : 2;
  const date = addBusinessDays(from, prepDays + TRANSIT_DAYS);
  date.setHours(0, 0, 0, 0);
  return date;
}

/** Date lisible dans la langue affichee : « mardi 4 aout ».
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
