/** Internationalisation de l'interface. */
import fr from "./dictionaries/fr.js";
import en from "./dictionaries/en.js";
import es from "./dictionaries/es.js";

export const LANGS = [
  { code: "fr", label: "Français" },
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
];

const DICTIONARIES = { fr, en, es };
const FALLBACK = "fr";

/** Construit la fonction de traduction pour une langue.
 *
 * Une entrée peut porter ses formes de pluriel, `{ one, other }` : la forme
 * suit `vars.n` selon les règles de la langue (en français, 0 et 1 sont au
 * singulier, en anglais seul 1 l'est).
 * @param {string} lang code de langue
 * @returns {(key: string, vars?: Record<string, unknown>) => string}
 */
export function translator(lang) {
  const code = DICTIONARIES[lang] ? lang : FALLBACK;
  const dict = DICTIONARIES[code];
  const regles = new Intl.PluralRules(code);

  return (key, vars) => {
    let text = dict[key] ?? DICTIONARIES[FALLBACK][key] ?? key;
    if (typeof text === "object") {
      const forme = regles.select(Number(vars?.n ?? 0));
      text = text[forme] ?? text.other;
    }
    if (vars) {
      for (const name of Object.keys(vars)) {
        text = text.replaceAll(`{${name}}`, vars[name]);
      }
    }
    return text;
  };
}

// En developpement, on signale les cles manquantes des le chargement plutot
// que de les decouvrir en naviguant dans une langue secondaire.
if (import.meta.env.DEV) {
  const reference = Object.keys(DICTIONARIES[FALLBACK]);
  for (const [code, dict] of Object.entries(DICTIONARIES)) {
    if (code === FALLBACK) continue;
    const missing = reference.filter((key) => !(key in dict));
    if (missing.length > 0) {
      console.warn(`[i18n] ${missing.length} cle(s) manquante(s) en "${code}" :`, missing);
    }
  }
}
