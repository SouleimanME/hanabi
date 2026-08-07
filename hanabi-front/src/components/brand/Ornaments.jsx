/** Ornements decoratifs : motifs traditionnels japonais dessines en SVG.
 *
 * Aucune image n'est telechargee : ces motifs sont generes, comme les visuels
 * produits de `ProductArt`. Trois avantages concrets - ils pesent quelques
 * centaines d'octets, restent nets a toutes les resolutions, et suivent le
 * theme clair/sombre puisqu'ils sont peints avec `currentColor`.
 *
 * Tous sont purement decoratifs, donc `aria-hidden` : un lecteur d'ecran ne
 * doit pas annoncer une frise de vagues.
 */
import { memo } from "react";

/**
 * Seigaiha (青海波), « vagues de la mer bleue » - frise d'arcs concentriques.
 *
 * Sert de separateur entre deux sections. Le motif est declare une fois dans
 * <pattern> puis repete par le navigateur : la taille du fichier ne depend pas
 * de la largeur a couvrir.
 */
export const SeigaihaBand = memo(function SeigaihaBand({ height = 46 }) {
  return (
    <svg
      className="ornament seigaiha"
      style={{ height }}
      aria-hidden="true"
      preserveAspectRatio="none"
      viewBox="0 0 120 40"
    >
      <defs>
        <pattern id="seigaiha-p" width="40" height="20" patternUnits="userSpaceOnUse">
          {/* Trois arcs emboites, decales d'un demi-motif pour que les rangees
              s'imbriquent comme les ecailles d'une vague. */}
          <g fill="none" stroke="currentColor" strokeWidth="1.4">
            {[0, 20, 40].map((cx) => (
              <g key={cx}>
                <path d={`M${cx - 18} 20 A18 18 0 0 1 ${cx + 18} 20`} />
                <path d={`M${cx - 12} 20 A12 12 0 0 1 ${cx + 12} 20`} />
                <path d={`M${cx - 6} 20 A6 6 0 0 1 ${cx + 6} 20`} />
              </g>
            ))}
            {[10, 30].map((cx) => (
              <g key={"o" + cx} transform="translate(0 10)">
                <path d={`M${cx - 18} 20 A18 18 0 0 1 ${cx + 18} 20`} />
                <path d={`M${cx - 12} 20 A12 12 0 0 1 ${cx + 12} 20`} />
                <path d={`M${cx - 6} 20 A6 6 0 0 1 ${cx + 6} 20`} />
              </g>
            ))}
          </g>
        </pattern>
      </defs>
      <rect width="120" height="40" fill="url(#seigaiha-p)" />
    </svg>
  );
});

/**
 * Fuji au soleil levant - silhouette posee en fond de pied de page.
 *
 * Le disque solaire et la montagne sont peints avec `currentColor` a des
 * opacites differentes, ce qui evite de coder en dur des couleurs qui
 * jureraient avec l'un des deux themes.
 */
export const FujiScene = memo(function FujiScene() {
  return (
    <div className="fuji-scene" aria-hidden="true">
      {/* Le soleil est un cercle CSS et non un <circle> SVG : le dessin est
          etire horizontalement pour epouser la largeur du pied de page (voir
          plus bas), ce qui transformerait un cercle en ellipse. */}
      <span className="fuji-sun" />
      <svg
        className="ornament fuji"
        viewBox="0 0 1200 200"
        /* `none` : le paysage epouse exactement la zone, sans rognage ni bande
         * vide. C'est le reglage qui corrige le defaut precedent - avec
         * `slice`, le dessin etait agrandi pour couvrir la largeur et son
         * sommet sortait de la boite, laissant une montagne decapitee et un
         * grand vide au-dessus.
         *
         * L'etirement horizontal est ici sans consequence : une chaine de
         * montagnes plus large reste une chaine de montagnes. Tout ce qui ne
         * tolere pas la deformation, comme le soleil, est sorti du SVG. */
        preserveAspectRatio="none"
      >
        {/* Collines lointaines, en arriere-plan. */}
        <path
          d="M0 200 L70 150 L150 172 L250 132 L330 166 L430 140 L520 170 L610 138
             L700 168 L790 144 L880 172 L980 136 L1070 168 L1150 148 L1200 166 L1200 200 Z"
          fill="currentColor"
          opacity="0.07"
        />

        {/* Fuji. Le sommet est volontairement decentre : une montagne
            parfaitement centree fait decor de theatre. */}
        <path d="M300 200 L730 52 L757 70 L785 52 L1160 200 Z" fill="currentColor" opacity="0.12" />

        {/* Calotte neigeuse : suit les deux versants, puis redescend en dents
            de scie irregulieres, comme la neige qui fond par coulees. */}
        <path
          d="M730 52 L757 70 L785 52 L872 100 L849 88 L824 106 L800 90 L776 108
             L752 90 L727 104 L701 88 L676 106 L651 100 Z"
          fill="currentColor"
          opacity="0.2"
        />

        {/* Nappes de brume : elles coupent la montagne et donnent la profondeur. */}
        <g fill="currentColor" opacity="0.08">
          <rect x="120" y="150" width="380" height="7" rx="3.5" />
          <rect x="600" y="136" width="440" height="7" rx="3.5" />
          <rect x="340" y="172" width="560" height="7" rx="3.5" />
          <rect x="920" y="160" width="260" height="7" rx="3.5" />
        </g>
      </svg>
    </div>
  );
});

/**
 * Kamon (家紋) - blason circulaire stylise, en filigrane derriere une section.
 * Trois anneaux et six petales, dans l'esprit d'une fleur de feu vue de face.
 */
export const Kamon = memo(function Kamon({ size = 320 }) {
  const petals = [0, 60, 120, 180, 240, 300];
  return (
    // Le blason deborde volontairement du cadre de sa section. L'enveloppe qui
    // le rogne est indispensable : sans elle, le depassement s'ajoute a la
    // largeur du document et ouvre un defilement horizontal. La page glisse
    // alors sous l'en-tete et le grain de papier, tous deux en `position:
    // fixed`, ce qui donne l'impression que le site se dedouble.
    //
    // Le rognage est porte par le composant, et non par les sections qui
    // l'utilisent : d'une part aucun appelant ne peut oublier de s'en occuper,
    // d'autre part poser `overflow: hidden` sur une section rognerait aussi les
    // menus deroulants qu'elle contient.
    <span className="kamon-clip" aria-hidden="true">
      <svg className="ornament kamon" width={size} height={size} viewBox="0 0 200 200">
        <g fill="none" stroke="currentColor" strokeWidth="1.6">
          <circle cx="100" cy="100" r="94" />
          <circle cx="100" cy="100" r="76" />
          <circle cx="100" cy="100" r="20" />
          {petals.map((a) => (
            <ellipse key={a} cx="100" cy="58" rx="17" ry="35" transform={`rotate(${a} 100 100)`} />
          ))}
        </g>
      </svg>
    </span>
  );
});
