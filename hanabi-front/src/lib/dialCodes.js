/** Indicatifs telephoniques proposes a l'inscription.
 *
 * Liste volontairement courte : la boutique ne livre pour l'instant qu'en
 * Europe de l'Ouest francophone et limitrophe. Le champ `code` est un code
 * ISO 3166-1 alpha-2, utilise pour construire l'URL du drapeau.
 */
export const DIAL_CODES = [
  { code: "FR", dial: "+33", label: "France" },
  { code: "MC", dial: "+377", label: "Monaco" },
  { code: "AD", dial: "+376", label: "Andorre" },
  { code: "CH", dial: "+41", label: "Suisse" },
  { code: "BE", dial: "+32", label: "Belgique" },
  { code: "LU", dial: "+352", label: "Luxembourg" },
  { code: "ES", dial: "+34", label: "Espagne" },
  { code: "DE", dial: "+49", label: "Allemagne" },
  { code: "NL", dial: "+31", label: "Pays-Bas" },
];
