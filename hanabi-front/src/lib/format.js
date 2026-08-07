/** Formatage des montants.
 *
 * Les prix circulent en centimes (entiers) de bout en bout pour eviter les
 * erreurs d'arrondi des flottants. La conversion en euros n'a lieu qu'ici,
 * au moment de l'affichage.
 */

const LOCALES = { fr: "fr-FR", en: "en-IE", es: "es-ES" };

/**
 * Construit un formateur de prix pour la langue courante.
 * @param {string} lang code de langue ("fr", "en", "es")
 * @returns {(cents: number) => string} ex. 6900 -> "69,00 €"
 */
export function createPriceFormatter(lang) {
  const locale = LOCALES[lang] ?? LOCALES.fr;
  const formatter = new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" });

  // Les seuils sont des nombres ronds : « offerte des 80 € » se lit mieux que
  // « offerte des 80,00 € », qui donne a un palier commercial l'air d'un
  // montant a payer. Les centimes reapparaissent des qu'il y en a.
  const rounded = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
  });

  const format = (cents) => formatter.format(cents / 100);
  format.short = (cents) => (cents % 100 === 0 ? rounded : formatter).format(cents / 100);
  return format;
}
