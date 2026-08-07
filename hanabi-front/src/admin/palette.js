/** Palette des graphiques du back-office, dans les deux themes.
 *
 * Ces valeurs ne sont pas choisies a l'oeil : elles sortent d'une recherche sous
 * contrainte puis d'un validateur. Les criteres, par theme :
 *
 *   - clarte OKLCH dans la bande du mode, faute de quoi une couleur disparait
 *     dans le fond ou l'eblouit ;
 *   - chroma >= 0,10, en dessous duquel une teinte se lit comme du gris et cesse
 *     de porter une identite ;
 *   - separation >= 8 (distance OKLab x100) entre voisines sous protanopie et
 *     deuteranopie simulees, et >= 15 en vision normale ;
 *   - contraste >= 3:1 sur le fond du theme.
 *
 * Le theme clair n'est pas une inversion du sombre. Une couleur lisible sur du
 * noir se dissout sur du papier : chaque teinte a son propre pas de clarte, la
 * meme famille des deux cotes. Ce que l'on conserve, c'est **l'ordre des
 * emplacements** - la couleur suit l'entite, jamais son rang. Une serie garde
 * donc sa famille de teinte en changeant de theme.
 *
 * Mesures obtenues :
 *   sombre (#16140F) : 14,9 sous deuteranopie, 21,3 en vision normale
 *   clair  (#FAF7F1) : 15,2 sous deuteranopie, 22,1 en vision normale
 *
 * Les valeurs vivent dans le CSS sous forme de variables : c'est lui qui bascule
 * d'un theme a l'autre, et les graphiques lisent `var(--ch-serie-N)` sans jamais
 * savoir quel theme est actif.
 */

/** Emplacements de series, dans l'ordre. Au-dela de cinq, on regroupe dans
 *  « autres » plutot que de fabriquer une teinte de plus : une couleur inventee
 *  redevient indistinguable sous daltonisme. */
export const SERIES = [
  "var(--ch-serie-1)", // rouge hanabi, couleur de marque
  "var(--ch-serie-2)", // bleu
  "var(--ch-serie-3)", // vert
  "var(--ch-serie-4)", // prune
  "var(--ch-serie-5)", // or
];

/** Rampe sequentielle des cartes de chaleur : une seule teinte, cinq pas de
 *  clarte. Jamais d'arc-en-ciel pour une magnitude, l'oeil n'y lit aucun ordre. */
export const SEQUENTIAL = [
  "var(--ch-heat-1)",
  "var(--ch-heat-2)",
  "var(--ch-heat-3)",
  "var(--ch-heat-4)",
  "var(--ch-heat-5)",
];

/** Couleurs d'etat, reservees et distinctes des series : une couleur d'etat ne
 *  doit jamais se faire passer pour une serie. Toujours accompagnees d'un
 *  libelle - jamais la couleur seule. */
export const STATUS = {
  good: "var(--ch-good)",
  warning: "var(--ch-warn)",
  critical: "var(--ch-bad)",
};

/** Habillage. La grille se tient un ton au-dessus du fond, en trait plein : un
 *  pointille se lirait comme un seuil. */
export const CHART = {
  surface: "var(--ch-surface)",
  grid: "var(--ch-grid)",
  crosshair: "var(--ch-crosshair)",
  empty: "var(--ch-heat-0)",
};

/** Etat d'une valeur par rapport a des reperes donnes. */
export function statusTone(value, { bon, moyen }) {
  if (value >= bon) return "good";
  if (value >= moyen) return "warning";
  return "critical";
}
