/** Internationalisation de l'interface.
 *
 * Repartition des responsabilites :
 *   - les libelles de l'interface sont traduits ici, cote client ;
 *   - le contenu produit (nom, description) est traduit cote serveur, dans
 *     `app/translations.py`, car il vient de la base.
 *
 * Pour ajouter une langue : creer `dictionaries/<code>.js`, l'enregistrer
 * dans DICTIONARIES et LANGS ci-dessous, puis ajouter la langue cote backend.
 */
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

/**
 * Construit la fonction de traduction pour une langue.
 *
 * Une cle manquante retombe sur le francais, puis sur la cle elle-meme :
 * l'interface reste lisible meme si une traduction a ete oubliee.
 *
 * @param {string} lang code de langue
 * @returns {(key: string, vars?: Record<string, unknown>) => string}
 */
export function translator(lang) {
  const dict = DICTIONARIES[lang] ?? DICTIONARIES[FALLBACK];

  return (key, vars) => {
    let text = dict[key] ?? DICTIONARIES[FALLBACK][key] ?? key;
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
