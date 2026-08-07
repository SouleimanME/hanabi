/** Calcul de la date de la prochaine serie.
 *
 * La boutique fonctionne par sorties hebdomadaires : chaque vendredi a 19 h.
 * Le compte a rebours de la page d'accueil s'appuie sur cette date.
 *
 * Le nom du fichier et des constantes conserve le terme « drop », interne au
 * code. Le vocabulaire montre au visiteur parle de serie et de selection.
 */

const FRIDAY = 5; // getDay() : 0 = dimanche, 5 = vendredi
const DROP_HOUR = 19;

/** Renvoie la date du prochain vendredi 19 h (aujourd'hui si l'heure n'est pas passee). */
export function nextDropDate(from = new Date()) {
  const target = new Date(from);
  target.setHours(DROP_HOUR, 0, 0, 0);

  let daysAhead = (FRIDAY - from.getDay() + 7) % 7;
  // Si on est vendredi mais que 19 h est deja passe, on vise la semaine suivante.
  if (daysAhead === 0 && from > target) daysAhead = 7;

  target.setDate(target.getDate() + daysAhead);
  return target;
}
