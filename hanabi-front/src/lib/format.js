/** Formatage des montants. */

const LOCALES = { fr: "fr-FR", en: "en-IE", es: "es-ES" };

/** Construit un formateur de prix pour la langue courante.
 * @param {string} lang code de langue ("fr", "en", "es")
 * @returns {(cents: number) => string} ex. 6900 -> "69,00 €"
 */
export function createPriceFormatter(lang) {
  const locale = LOCALES[lang] ?? LOCALES.fr;
  const formatter = new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" });

  // Les seuils sont des nombres ronds
  const rounded = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
  });

  const format = (cents) => formatter.format(cents / 100);
  format.short = (cents) => (cents % 100 === 0 ? rounded : formatter).format(cents / 100);
  return format;
}
