/** Acces au localStorage tolerant aux pannes.
 *
 * Le localStorage leve une exception dans plusieurs cas reels : navigation
 * privee sur Safari, quota depasse, cookies tiers bloques. On absorbe l'erreur
 * et on retombe sur la valeur par defaut plutot que de casser le rendu.
 */

const PREFIX = "hanabi:";

export const storage = {
  /** Lit une valeur JSON, ou `fallback` si absente ou illisible. */
  get(key, fallback) {
    try {
      const raw = localStorage.getItem(PREFIX + key);
      return raw == null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },

  /** Ecrit une valeur JSON. Echoue silencieusement si le stockage est indisponible. */
  set(key, value) {
    try {
      localStorage.setItem(PREFIX + key, JSON.stringify(value));
    } catch {
      /* quota depasse ou stockage desactive : on ignore */
    }
  },
};
