/** Visuel d'un produit : photo si disponible, composition generee sinon.
 *
 * Le champ `art` est stocke en base sous la forme "forme,couleur1,couleur2"
 * (ex. "enso,#224A3F,#E4D7BF"), ou directement une URL d'image. Les photos
 * televersees depuis le back-office prennent toujours le dessus.
 *
 * Les compositions generees ne sont pas un pis-aller en attendant des photos :
 * elles tiennent lieu d'identite visuelle. Un catalogue de douze aplats a deux
 * couleurs se lit comme un gabarit non rempli ; on cherche ici l'inverse, une
 * serigraphie sur papier - profondeur, matiere, lumiere rasante - qui donne au
 * catalogue l'air d'avoir ete dessine plutot que reserve.
 *
 * PARTI PRIS DE PERFORMANCE : aucun filtre SVG. `feGaussianBlur` et
 * `feTurbulence` donneraient du flou et du grain a moindre effort, mais un
 * filtre se rastérise a chaque changement de taille et douze cartes en
 * afficheraient douze. Toute la profondeur vient donc de degrades et de
 * superpositions, que le navigateur rastérise une fois et compose ensuite sans
 * repeindre.
 */
import { memo } from "react";

/** Eclaircit ou assombrit une couleur hexadecimale.
 *
 * `facteur` negatif assombrit, positif eclaircit, sur une echelle de -1 a 1.
 * Sert a fabriquer les deux bouts d'un degrade a partir d'une seule teinte :
 * la palette du catalogue n'en fournit que deux par produit, et un volume
 * demande au moins une lumiere et une ombre.
 */
function teinte(hex, facteur) {
  const propre = /^#[0-9a-f]{6}$/i.test(hex || "") ? hex : "#888888";
  const canal = (i) => {
    const v = parseInt(propre.slice(1 + i * 2, 3 + i * 2), 16);
    const cible = facteur < 0 ? 0 : 255;
    return Math.round(v + (cible - v) * Math.abs(facteur));
  };
  return `#${[0, 1, 2].map((i) => canal(i).toString(16).padStart(2, "0")).join("")}`;
}

/** Identifiant stable et unique par combinaison forme/couleurs.
 *
 * Les degrades d'un SVG vivent dans un espace de noms partage par tout le
 * document : deux cartes qui declareraient `id="grad"` se voleraient leur
 * remplissage. La cle derive donc du contenu - deux visuels identiques
 * partagent alors le meme degrade, ce qui est exactement ce qu'on veut.
 */
function cle(art) {
  let h = 0;
  for (let i = 0; i < art.length; i++) h = (h * 31 + art.charCodeAt(i)) | 0;
  return `a${(h >>> 0).toString(36)}`;
}

export const ProductArt = memo(function ProductArt({ art, small }) {
  // Si c'est une vraie photo (URL ou base64), on l'affiche directement.
  if (typeof art === "string" && (art.startsWith("http") || art.startsWith("data:"))) {
    return (
      <img
        src={art}
        alt=""
        className="art"
        style={{ objectFit: "cover", width: "100%", height: "100%", display: "block" }}
        loading="lazy"
      />
    );
  }

  const brut = typeof art === "string" ? art : Array.isArray(art) ? art.join(",") : "";
  const [shape, c1 = "#D8452B", c2 = "#EFE7D6"] = brut.split(",");
  const id = cle(brut);
  const r = small ? 6 : 8;

  // Trois teintes tirees de la couleur principale : la lumiere, la couleur
  // pleine, l'ombre. C'est ce qui donne du volume a une forme plate.
  const clair = teinte(c1, 0.28);
  const sombre = teinte(c1, -0.3);

  const defs = (
    <defs>
      {/* Lumiere rasante venant du haut-gauche, comme un objet pose pres d'une
          fenetre. Le meme angle sur tout le catalogue fait tenir l'ensemble. */}
      <linearGradient id={`${id}-f`} x1="0" y1="0" x2="0.75" y2="1">
        <stop offset="0" stopColor={clair} />
        <stop offset="0.55" stopColor={c1} />
        <stop offset="1" stopColor={sombre} />
      </linearGradient>
      {/* Fond : halo tres doux, decentre, qui detache le motif du papier. */}
      <radialGradient id={`${id}-b`} cx="0.34" cy="0.28" r="0.92">
        <stop offset="0" stopColor={c2} stopOpacity="0.5" />
        <stop offset="0.6" stopColor={c2} stopOpacity="0.16" />
        <stop offset="1" stopColor={c2} stopOpacity="0.03" />
      </radialGradient>
      {/* Ombre portee, en degrade plutot qu'en flou : meme resultat a l'oeil,
          sans le cout d'un filtre. */}
      <radialGradient id={`${id}-o`} cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor={sombre} stopOpacity="0.34" />
        <stop offset="0.62" stopColor={sombre} stopOpacity="0.12" />
        <stop offset="1" stopColor={sombre} stopOpacity="0" />
      </radialGradient>
    </defs>
  );

  const remplissage = `url(#${id}-f)`;

  let body = null;

  if (shape === "enso") {
    // Cercle zen trace d'un seul geste : l'ouverture et l'inegalite du trait
    // sont le sujet, on les accentue par une seconde passe plus fine.
    body = (
      <g>
        <circle
          cx="100"
          cy="100"
          r="60"
          fill="none"
          stroke={remplissage}
          strokeWidth="17"
          strokeLinecap="round"
          strokeDasharray="322 100"
          transform="rotate(40 100 100)"
        />
        <circle
          cx="100"
          cy="100"
          r="60"
          fill="none"
          stroke={clair}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray="150 272"
          opacity="0.5"
          transform="rotate(52 100 100)"
        />
        <circle cx="150" cy="64" r={r + 2} fill={c2} />
      </g>
    );
  } else if (shape === "wave") {
    // Seigaiha : les rangees s'eclaircissent vers le haut, ce qui creuse une
    // perspective la ou toutes les vagues avaient auparavant le meme poids.
    body = (
      <g fill="none" strokeLinecap="round">
        {[52, 100, 148].map((y, ri) => (
          <g
            key={ri}
            stroke={ri === 1 ? remplissage : ri === 0 ? clair : sombre}
            strokeWidth={5 + ri * 0.9}
            opacity={0.55 + ri * 0.22}
          >
            {[5, 55, 105, 155].map((x) => (
              <g key={x}>
                <path d={`M${x - 26} ${y} A26 26 0 0 1 ${x + 26} ${y}`} />
                <path d={`M${x - 14} ${y} A14 14 0 0 1 ${x + 14} ${y}`} />
              </g>
            ))}
          </g>
        ))}
      </g>
    );
  } else if (shape === "fan") {
    const pv = [100, 170];
    const ribs = [-72, -48, -24, 0, 24, 48, 72].map((a) => {
      const rad = ((a - 90) * Math.PI) / 180;
      return [pv[0] + 98 * Math.cos(rad), pv[1] + 98 * Math.sin(rad)];
    });
    body = (
      <g>
        <ellipse cx="100" cy="176" rx="62" ry="9" fill={`url(#${id}-o)`} />
        <path
          d={`M${pv[0]} ${pv[1]} L${ribs[0][0]} ${ribs[0][1]} A98 98 0 0 1 ${ribs[6][0]} ${ribs[6][1]} Z`}
          fill={remplissage}
        />
        {/* Liseré clair sur le bord exterieur : un eventail a une tranche. */}
        <path
          d={`M${ribs[0][0]} ${ribs[0][1]} A98 98 0 0 1 ${ribs[6][0]} ${ribs[6][1]}`}
          fill="none"
          stroke={clair}
          strokeWidth="3.5"
          opacity="0.7"
        />
        {ribs.map((p, i) => (
          <line
            key={i}
            x1={pv[0]}
            y1={pv[1]}
            x2={p[0]}
            y2={p[1]}
            stroke={c2}
            strokeWidth="2.2"
            opacity="0.55"
          />
        ))}
        <circle cx={pv[0]} cy={pv[1]} r={r} fill={sombre} />
      </g>
    );
  } else if (shape === "asanoha") {
    const cx = 100;
    const cy = 100;
    const R = 66;
    const pts = [0, 60, 120, 180, 240, 300].map((a) => [
      cx + R * Math.cos((a * Math.PI) / 180),
      cy + R * Math.sin((a * Math.PI) / 180),
    ]);
    body = (
      <g strokeLinejoin="round" strokeLinecap="round" fill="none">
        {/* Trame secondaire en retrait : le motif du chanvre se repete a
            l'infini sur un tissu, un seul hexagone isolé faisait maquette. */}
        <g stroke={c2} strokeWidth="2" opacity="0.45">
          <polygon
            points={pts
              .map((p) => [cx + (p[0] - cx) * 1.7, cy + (p[1] - cy) * 1.7].join(","))
              .join(" ")}
          />
        </g>
        <polygon
          points={pts.map((p) => p.join(",")).join(" ")}
          stroke={remplissage}
          strokeWidth="4.5"
        />
        {pts.map((p, i) => (
          <line key={i} x1={cx} y1={cy} x2={p[0]} y2={p[1]} stroke={remplissage} strokeWidth="4" />
        ))}
        {pts.map((p, i) => (
          <line
            key={`e${i}`}
            x1={p[0]}
            y1={p[1]}
            x2={pts[(i + 2) % 6][0]}
            y2={pts[(i + 2) % 6][1]}
            stroke={c2}
            strokeWidth="2.4"
            opacity="0.8"
          />
        ))}
        <circle cx={cx} cy={cy} r={r - 2} fill={clair} stroke="none" />
      </g>
    );
  } else if (shape === "torii") {
    body = (
      <g>
        <ellipse cx="100" cy="166" rx="58" ry="8" fill={`url(#${id}-o)`} />
        <g fill={remplissage}>
          <rect x="28" y="44" width="144" height="16" rx="4" />
          <rect x="44" y="74" width="112" height="11" rx="2.5" />
          <rect x="57" y="60" width="16" height="102" rx="1.5" />
          <rect x="127" y="60" width="16" height="102" rx="1.5" />
        </g>
        {/* Aretes eclairees : sans elles, le portique reste une silhouette. */}
        <g fill={clair} opacity="0.62">
          <rect x="28" y="44" width="144" height="4" rx="2" />
          <rect x="57" y="60" width="4.5" height="102" />
          <rect x="127" y="60" width="4.5" height="102" />
        </g>
        <circle cx="100" cy="32" r={r} fill={c2} />
      </g>
    );
  } else if (shape === "moon") {
    body = (
      <g>
        <circle cx="100" cy="88" r="56" fill={remplissage} />
        {/* Croissant d'ombre : un disque plat n'est pas une lune. */}
        <circle cx="122" cy="76" r="50" fill={sombre} opacity="0.22" />
        <circle cx="82" cy="72" r="9" fill={clair} opacity="0.35" />
        <circle cx="112" cy="104" r="6" fill={clair} opacity="0.22" />
        {/* Bandes de brume, degradees vers l'exterieur. */}
        <g fill={c2}>
          <rect x="24" y="122" width="84" height="11" rx="5.5" opacity="0.55" />
          <rect x="84" y="142" width="88" height="11" rx="5.5" opacity="0.4" />
          <rect x="44" y="160" width="58" height="9" rx="4.5" opacity="0.26" />
        </g>
      </g>
    );
  } else if (shape === "sakura") {
    // Fleur de cerisier : cinq petales echancres, la signature florale du
    // catalogue. Chaque petale porte son propre degrade par rotation.
    const petale = "M100 100 C 88 74, 88 50, 100 34 C 112 50, 112 74, 100 100 Z";
    body = (
      <g transform="translate(0,-8)">
        <ellipse cx="100" cy="168" rx="46" ry="7" fill={`url(#${id}-o)`} />
        {[0, 72, 144, 216, 288].map((a) => (
          <g key={a} transform={`rotate(${a} 100 100)`}>
            <path d={petale} fill={remplissage} />
            <path d={petale} fill={clair} opacity="0.28" transform="scale(0.62) translate(62,62)" />
          </g>
        ))}
        <circle cx="100" cy="100" r={r + 3} fill={c2} />
        <circle cx="100" cy="100" r={r - 1} fill={clair} opacity="0.7" />
      </g>
    );
  } else if (shape === "bol") {
    // Bol : une ellipse pour l'ouverture, une calotte pour le corps. Le liseré
    // clair sur la levre est ce qui fait lire un contenant plutot qu'un demi-
    // disque.
    body = (
      <g>
        <ellipse cx="100" cy="164" rx="54" ry="8" fill={`url(#${id}-o)`} />
        <path d="M42 92 A58 58 0 0 0 158 92 Z" fill={remplissage} />
        <ellipse cx="100" cy="92" rx="58" ry="15" fill={sombre} />
        <ellipse cx="100" cy="92" rx="58" ry="15" fill="none" stroke={clair} strokeWidth="3" />
        <ellipse cx="100" cy="94" rx="44" ry="10" fill={c2} opacity="0.32" />
        <rect x="86" y="150" width="28" height="9" rx="4" fill={sombre} />
      </g>
    );
  } else if (shape === "baguettes") {
    body = (
      <g>
        <ellipse cx="100" cy="170" rx="50" ry="7" fill={`url(#${id}-o)`} />
        {[-9, 9].map((dx, i) => (
          <g key={dx} transform={`rotate(${dx} 100 100)`}>
            <rect x={96 + dx * 1.6} y="32" width="9" height="128" rx="4.5" fill={remplissage} />
            <rect
              x={96 + dx * 1.6}
              y="32"
              width="3"
              height="128"
              rx="1.5"
              fill={clair}
              opacity={0.5 - i * 0.14}
            />
          </g>
        ))}
        <circle cx="100" cy="172" r={r - 1} fill={c2} />
      </g>
    );
  } else if (shape === "neko") {
    // Silhouette de chat assis, oreilles marquees : le motif le plus lisible
    // du catalogue en petit format.
    body = (
      <g>
        <ellipse cx="100" cy="170" rx="48" ry="8" fill={`url(#${id}-o)`} />
        <path d="M74 74 L68 40 L94 60 Z" fill={remplissage} />
        <path d="M126 74 L132 40 L106 60 Z" fill={remplissage} />
        <circle cx="100" cy="86" r="34" fill={remplissage} />
        <path d="M70 116 Q100 106 130 116 L138 164 Q100 174 62 164 Z" fill={remplissage} />
        <circle cx="88" cy="82" r="4.5" fill={sombre} />
        <circle cx="112" cy="82" r="4.5" fill={sombre} />
        <circle cx="100" cy="94" r="3.5" fill={c2} />
        <path d="M78 60 A34 34 0 0 1 122 60" fill={clair} opacity="0.24" />
      </g>
    );
  } else {
    // Forme inconnue : composition neutre plutot qu'un cadre vide. Le catalogue
    // ne doit jamais afficher de trou, meme si la base contient une valeur
    // inattendue.
    body = (
      <g>
        <ellipse cx="100" cy="164" rx="50" ry="8" fill={`url(#${id}-o)`} />
        <circle cx="100" cy="96" r="52" fill={remplissage} />
        <circle cx="100" cy="96" r="52" fill="none" stroke={clair} strokeWidth="3" opacity="0.5" />
        <circle cx="100" cy="96" r="22" fill={c2} opacity="0.35" />
      </g>
    );
  }

  return (
    <svg viewBox="0 0 200 200" className="art" aria-hidden="true">
      {defs}
      {/* Papier : un aplat, puis le halo qui decentre la lumiere. */}
      <rect width="200" height="200" fill={c2} opacity="0.09" />
      <rect width="200" height="200" fill={`url(#${id}-b)`} />
      {body}
    </svg>
  );
});
