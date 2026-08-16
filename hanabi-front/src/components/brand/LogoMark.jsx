/** Embleme Hanabi : mitsudomoe, trois virgules dans un cercle.
 *
 * Le tomoe (巴) est le motif des tuiles de sanctuaire, des tambours taiko et
 * des blasons de samourai. Il figure la giration - l'eau, la flamme, le
 * tonnerre. Le mitsudomoe (三ツ巴) en aligne trois dans un cercle.
 *
 * POURQUOI CE MOTIF PLUTOT QU'UN TORII OU UN CERISIER. Les grandes marques
 * japonaises ne representent pas le Japon, elles reprennent la grammaire du
 * kamon, le blason familial : enfermement dans un cercle, aplats pleins,
 * reduction extreme. Les trois losanges de Mitsubishi viennent du blason des
 * Iwasaki, l'hexagone de Kikkoman d'une carapace de tortue. Aucune ne dessine
 * un paysage. L'embleme precedent empilait un torii, un soleil et un sakura :
 * trois cliches corrects et interchangeables avec cent autres boutiques.
 *
 * LES TETES VONT VERS L'EXTERIEUR, a l'inverse du mitsudomoe traditionnel qui
 * les place au centre et se lit comme un tourbillon qui aspire. Ici les queues
 * trainent derriere : ce n'est plus un remous, c'est une projection. Trois
 * etoiles qui viennent de partir, ce qui est exactement ce que raconte le nom
 * de la boutique.
 *
 * LE CENTRE RESTE VIDE. La bombe a deja eclate. C'est aussi ce qui sauve la
 * lisibilite en petit : verifie par rasterisation a 20 px, ou l'anneau et les
 * trois virgules restent quatre formes distinctes et le coeur garde un alpha
 * nul. Une masse pleine y serait devenue une tache.
 *
 * LES TRACES SONT FIGES, et c'est voulu : un blason se redessine a
 * l'identique, il ne se regenere pas a chaque rendu. La geometrie qui les a
 * produits, si l'on doit les refaire un jour : trois virgules a 120 degres
 * dans un carre de 104 centre en 52, spirale du rayon 27,5 vers 15, balayage
 * de -96 degres, demi-largeur de 10,2 a 0 en puissance 0,78, terminee par un
 * demi-cercle de tete. Une decroissance lineaire de la largeur donnait un
 * ruban et non une virgule ; des courbes de Bezier lachees donnaient trois
 * formes soudees en galette.
 */

const VIRGULES = [
  "M52.00 14.30L49.62 15.16L47.36 16.18L45.21 17.33L43.20 18.61L41.32 20.00L39.58 21.50L38.00 23.09L36.56 24.76L35.29 26.49L34.17 28.28L33.22 30.10L32.42 31.95L31.79 33.81L31.32 35.67L31.01 37.51L30.86 39.33L30.85 41.12L30.99 42.85L31.28 44.52L31.70 46.12L32.25 47.64L32.93 49.06L33.74 50.38L34.66 51.58L35.73 52.66L37.08 53.57L37.08 53.57L37.33 52.59L37.42 51.65L37.51 50.71L37.62 49.78L37.76 48.85L37.94 47.93L38.17 47.01L38.45 46.10L38.78 45.20L39.16 44.31L39.59 43.44L40.08 42.58L40.62 41.76L41.22 40.95L41.86 40.18L42.56 39.44L43.31 38.74L44.11 38.08L44.96 37.47L45.85 36.90L46.79 36.39L47.76 35.93L48.77 35.52L49.82 35.18L50.90 34.91A10.2 10.2 0 1 1 52.00 14.30Z",
  "M84.65 70.85L85.09 68.36L85.34 65.89L85.42 63.46L85.32 61.07L85.05 58.75L84.62 56.50L84.04 54.33L83.31 52.25L82.45 50.28L81.46 48.42L80.36 46.68L79.16 45.07L77.86 43.60L76.48 42.26L75.04 41.07L73.54 40.02L72.00 39.13L70.43 38.38L68.84 37.79L67.24 37.36L65.65 37.08L64.08 36.96L62.54 36.99L61.03 37.20L59.57 37.58L58.10 38.30L58.10 38.30L58.82 39.00L59.59 39.55L60.36 40.09L61.11 40.65L61.85 41.24L62.55 41.86L63.24 42.52L63.89 43.22L64.50 43.95L65.08 44.73L65.62 45.54L66.11 46.39L66.56 47.27L66.96 48.19L67.30 49.13L67.59 50.11L67.83 51.11L68.00 52.13L68.11 53.17L68.15 54.23L68.13 55.29L68.04 56.37L67.88 57.44L67.65 58.52L67.35 59.59A10.2 10.2 0 1 1 84.65 70.85Z",
  "M19.35 70.85L21.29 72.48L23.30 73.93L25.37 75.21L27.48 76.32L29.63 77.25L31.80 78.00L33.97 78.58L36.13 78.99L38.26 79.23L40.37 79.30L42.42 79.22L44.42 78.98L46.35 78.60L48.19 78.07L49.95 77.42L51.60 76.65L53.15 75.76L54.58 74.77L55.88 73.69L57.06 72.52L58.09 71.28L58.99 69.98L59.73 68.63L60.31 67.22L60.70 65.76L60.82 64.14L60.82 64.14L59.84 64.41L58.98 64.80L58.13 65.19L57.27 65.57L56.40 65.91L55.50 66.21L54.59 66.47L53.66 66.68L52.72 66.85L51.76 66.96L50.79 67.03L49.81 67.03L48.82 66.98L47.82 66.86L46.83 66.69L45.84 66.45L44.86 66.15L43.89 65.79L42.93 65.36L42.00 64.87L41.08 64.32L40.20 63.71L39.34 63.03L38.53 62.29L37.75 61.50A10.2 10.2 0 1 1 19.35 70.85Z",
];

export function LogoMark({ size = 34, title }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 104 104"
      /* Une seule encre. L'embleme herite de la couleur du texte, ce qui le
         rend juste sur la laque, sur le vermillon et sur le papier sans qu'on
         maintienne trois fichiers ni un jeu de variables CSS. */
      fill="currentColor"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : "true"}
      style={{ flexShrink: 0, display: "block" }}
    >
      <circle cx="52" cy="52" r="45" fill="none" stroke="currentColor" strokeWidth="5" />
      {VIRGULES.map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
