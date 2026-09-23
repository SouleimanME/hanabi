/** Visuel d'un produit : photo si l'on en a une, blason sinon. */
import { memo, useId } from "react";
import { sourcesAdaptees } from "../../lib/images.js";

const KIRI = 2.4;

/* Formes des premieres versions du catalogue, encore presentes dans des lignes
   de commande anciennes. */
const FORMES_ANCIENNES = { enso: "kitsune", wave: "seigaiha", asanoha: "bandana" };

const HEX = /^#[0-9a-f]{6}$/i;

/** Eclaircit une couleur hexadecimale vers le blanc, de `facteur` (0 a 1). */
function eclaircir(hex, facteur) {
  const canal = (i) => {
    const v = parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16);
    return Math.round(v + (255 - v) * facteur);
  };
  return `#${[0, 1, 2].map((i) => canal(i).toString(16).padStart(2, "0")).join("")}`;
}

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const n2 = (v) => +v.toFixed(2);
const polaire = (cx, cy, r, deg) => [
  n2(cx + r * Math.cos((deg * Math.PI) / 180)),
  n2(cy + r * Math.sin((deg * Math.PI) / 180)),
];
const gelule = (x1, x2, y1, y2) => {
  const r = (y2 - y1) / 2;
  return `M${x1 + r} ${y1}H${x2 - r}A${r} ${r} 0 0 1 ${x2 - r} ${y2}H${x1 + r}A${r} ${r} 0 0 1 ${x1 + r} ${y1}Z`;
};

/** Dessine le blason `forme` avec l'encre `t`, la coupe etant peinte en `f`. */
function Blason({ forme, t, f }) {
  let cle = 0;
  const k = () => cle++;
  const plein = (d) => <path key={k()} d={d} fill={t} />;
  const creux = (d) => <path key={k()} d={d} fill={f} />;
  const trait = (d, l, c = t, bout = "round") => (
    <path
      key={k()}
      d={d}
      fill="none"
      stroke={c}
      strokeWidth={l}
      strokeLinecap={bout}
      strokeLinejoin="round"
    />
  );
  const coupe = (d, l = KIRI, bout = "butt") => trait(d, l, f, bout);
  /* Detourage : la forme est d'abord cernee d'une coupe, puis posee */
  const detoure = (d) => [trait(d, KIRI * 2, f), plein(d)];
  const rond = (x, y, r, c = t) => <circle key={k()} cx={x} cy={y} r={r} fill={c} />;
  const decale = (x, y, enfants) => <g transform={`translate(${x} ${y})`}>{enfants}</g>;

  switch (forme) {
    case "torii":
      return decale(0, -5, [
        plein("M9 24Q30 33 50 32Q70 33 91 24L88 32Q70 39.5 50 39Q30 39.5 12 32Z"),
        plein("M20 41.5H80V46.5H20Z"),
        plein("M47 49H53V56H47Z"),
        plein("M28 49H34L33 86H25Z"),
        plein("M66 49H72L75 86H67Z"),
        creux("M12 56.1H88V66.4H12Z"),
        plein("M14 58.5H86V64H14Z"),
      ]);

    case "baguettes": {
      const baguette = (y) =>
        `M11 ${y - 3.2}L87 ${y - 1.2}A1.2 1.2 0 0 1 87 ${y + 1.2}L11 ${y + 3.2}Z`;
      return (
        <g transform="rotate(38 50 50)">
          {plein(baguette(45))}
          {plein(baguette(55))}
          {coupe("M24 38V62", 1.6)}
          {coupe("M28 38V62", 1.6)}
        </g>
      );
    }

    case "moon":
      return decale(0, 4, [
        rond(52, 44, 30),
        ...detoure(gelule(62, 92, 45, 50)),
        ...detoure(gelule(8, 60, 55, 60)),
        ...detoure(gelule(34, 88, 65, 70)),
      ]);

    case "bol": {
      const baguette = (y) => `M20 ${y - 2.4}L78 ${y - 1}A1 1 0 0 1 78 ${y + 1}L20 ${y + 2.4}Z`;
      return (
        <>
          <g transform="rotate(-32 50 50)">
            {detoure(baguette(36))}
            {detoure(baguette(44))}
          </g>
          {detoure(gelule(11, 89, 43, 50))}
          {plein("M17 52H83A33 28 0 0 1 17 52Z")}
          {coupe("M14 61H86")}
          {coupe("M14 66.5H86")}
          {plein("M39 82.5H61V88H39Z")}
        </>
      );
    }

    case "suzu": {
      const cordon = "M8 15Q50 33 92 15";
      return (
        <>
          <circle cx="50" cy="25" r="6.5" fill="none" stroke={t} strokeWidth="3.6" />
          {rond(50, 59, 26)}
          {coupe("M20 57H80", 3)}
          {coupe("M50 67V85", 2.6)}
          {rond(50, 67, 3.6, f)}
          {trait(cordon, 3 + KIRI * 2, f)}
          {trait(cordon, 3)}
        </>
      );
    }

    case "fan": {
      const cx = 50;
      const cy = 78;
      const R = 50;
      const r = 23;
      const plis = 10;
      const angle = (i) => -152 + (124 * i) / plis;
      const bord = [];
      for (let i = 0; i <= plis; i++) bord.push(polaire(cx, cy, i % 2 ? R - 3 : R, angle(i)));
      const [ix0, iy0] = polaire(cx, cy, r, angle(0));
      const [ix1, iy1] = polaire(cx, cy, r, angle(plis));
      const papier = `M${ix0} ${iy0}L${bord.map((p) => p.join(" ")).join("L")}L${ix1} ${iy1}A${r} ${r} 0 0 0 ${ix0} ${iy0}Z`;
      const traits = [];
      for (let i = 0; i <= plis; i++) {
        const [bx, by] = polaire(cx, cy, r - KIRI, angle(i));
        traits.push(trait(`M${cx} ${cy}L${bx} ${by}`, 2));
        if (i > 0 && i < plis) {
          const [px, py] = polaire(cx, cy, r, angle(i));
          const [qx, qy] = polaire(cx, cy, R, angle(i));
          traits.push(coupe(`M${px} ${py}L${qx} ${qy}`, 1.6));
        }
      }
      return decale(0, -6, [plein(papier), ...traits, rond(cx, cy, 5.5), rond(cx, cy, 2, f)]);
    }

    case "kitsune":
      return (
        <>
          {plein(
            "M50 88L66 68L80 62L73 57Q83 49 81 40L79 12L60 29Q50 26 40 29L21 12L19 40Q17 49 27 57L20 62L34 68Z",
          )}
          {creux("M76.5 20L65 31L77 36Z")}
          {creux("M23.5 20L35 31L23 36Z")}
          {creux("M55 53Q63 44 73 43Q67 53 55 53Z")}
          {creux("M45 53Q37 44 27 43Q33 53 45 53Z")}
          {creux("M50 34L53.5 40.5L50 47L46.5 40.5Z")}
        </>
      );

    case "sakura": {
      const petale =
        "M50 44C35 39 28 29 30 19Q33 11.5 42 11.5Q47 11.5 50 17.5Q53 11.5 58 11.5Q67 11.5 70 19C72 29 65 39 50 44Z";
      const petales = [];
      const coupes = [];
      for (let i = 0; i < 5; i++) {
        petales.push(<path key={k()} transform={`rotate(${i * 72} 50 50)`} d={petale} fill={t} />);
        const a = -54 + i * 72;
        const [x0, y0] = polaire(50, 50, 5, a);
        const [x1, y1] = polaire(50, 50, 42, a);
        coupes.push(coupe(`M${x0} ${y0}L${x1} ${y1}`));
      }
      return decale(0, 3.6, [
        ...petales,
        rond(50, 50, 9),
        ...coupes,
        rond(50, 50, 5, f),
        rond(50, 50, 2.2),
      ]);
    }

    /* Bandana Sushi : le motif imprime plutot que le tissu. Un triangle seme de
       pois se lisait comme une part de pizza. */
    case "bandana":
      return decale(0, -2, [
        plein(gelule(22, 78, 52, 72)),
        ...detoure("M12 52Q22 34 50 32Q78 30 88 46Q70 54 50 53Q30 54 12 52Z"),
        coupe("M31 36.5L25 51"),
        coupe("M47 33.5L41 52.5"),
        coupe("M63 33L57 52.5"),
        coupe("M77 36.5L72 50"),
      ]);

    /* Chaque rang recouvre le precedent ; ce qui deborde du medaillon est
       repeint par un anneau de coupe. */
    case "seigaiha": {
      const vagues = [];
      for (let rang = 0, y = 4; y <= 106; rang++, y += 6.5) {
        for (let x = rang % 2 ? 0 : -13; x <= 113; x += 26) {
          vagues.push(
            rond(x, y, 13),
            rond(x, y, 10.6, f),
            rond(x, y, 8.2),
            rond(x, y, 5.8, f),
            rond(x, y, 3.4),
          );
        }
      }
      return (
        <>
          {vagues}
          <circle cx="50" cy="50" r="58" fill="none" stroke={f} strokeWidth="44" />
        </>
      );
    }

    case "neko":
      return decale(5, 0, [
        plein("M13 26A6 6 0 0 1 25 26V50Q25 56 36 58L34 66Q13 62 13 50Z"),
        plein("M34 32L33 12L47 23Z"),
        plein("M70 32L71 12L57 23Z"),
        <ellipse key={k()} cx="52" cy="38" rx="20" ry="16.5" fill={t} />,
        plein("M31 86Q27 64 36 53H68Q77 64 73 86Z"),
        trait("M40.5 39.5Q44.5 35 48.5 39.5", 2.4, f),
        trait("M55.5 39.5Q59.5 35 63.5 39.5", 2.4, f),
        coupe("M33 54Q52 62 71 54"),
        rond(52, 63, 6.8, f),
        rond(52, 63, 4.4),
        coupe("M49 64H55", 1.2),
      ]);

    case "futon": {
      const coussin = "M16 17Q50 26 84 17Q75 52 84 87Q50 78 16 87Q25 52 16 17Z";
      return (
        <>
          {plein(coussin)}
          {trait(coussin, 4)}
          <ellipse cx="55" cy="58" rx="19" ry="14" fill={f} />
          {rond(37, 51, 9.5, f)}
          {creux("M29.5 47L28 35.5L37 42Z")}
          {creux("M38 41.5L44 33L46.5 44Z")}
          {trait("M73 63Q69 76 52 75.5Q38 75 34.5 64", 5, f)}
          {trait("M47.5 44.5Q53 52 48.5 61", 2)}
          {trait("M71 63.5Q66.5 72 52 71.5Q42 71 38.5 64", 2)}
          {trait("M31 53.5q2.8 1.8 5.6 0", 1.8)}
        </>
      );
    }

    /* Forme inconnue : l'embleme de la maison plutot qu'un cadre vide */
    default:
      return (
        <>
          <circle cx="50" cy="50" r="34" fill="none" stroke={t} strokeWidth="4" />
          {rond(50, 50, 12)}
        </>
      );
  }
}

const estPhoto = (art) =>
  typeof art === "string" && (art.startsWith("http") || art.startsWith("data:"));

/* Scène de la fiche : le blason en laque, découpé à même la plaque de vermillon */
const SCENE = { trace: "#0A0605", fond: "#F4643F" };

/**
 * @param taille  valeur de `sizes` : la largeur affichée. Par défaut, une vignette.
 * @param priorite  image principale de l'écran : chargée tout de suite, en tête de file.
 */
export const ProductArt = memo(function ProductArt({
  art,
  alt = "",
  scene = false,
  taille = "96px",
  priorite = false,
}) {
  const idBrut = useId();

  if (estPhoto(art)) {
    // React pose les attributs dans l'ordre écrit : `src` en dernier, sinon le
    // navigateur télécharge la grande image avant de lire `loading` et `srcset`.
    return (
      <img
        alt={alt}
        className="art art-photo"
        width="1200"
        height="1200"
        loading={priorite ? "eager" : "lazy"}
        // React 18 ne connaît pas `fetchPriority` ; en minuscules, l'attribut passe tel quel
        // eslint-disable-next-line react/no-unknown-property
        fetchpriority={priorite ? "high" : undefined}
        decoding="async"
        sizes={taille}
        srcSet={sourcesAdaptees(art) ?? undefined}
        src={art}
      />
    );
  }

  const [formeBrute = "", c1 = "", c2 = "", option = ""] = String(art || "").split(",");
  const forme = FORMES_ANCIENNES[formeBrute] || formeBrute;
  const trace = scene ? SCENE.trace : HEX.test(c1) ? c1 : "#E0452A";
  const fond = scene ? SCENE.fond : HEX.test(c2) ? c2 : "#0A0605";
  // Sur la scène, un aplat : le vermillon est une surface, pas un éclairage
  const clair = scene ? fond : eclaircir(fond, luminance(fond) > 0.5 ? 0.45 : 0.1);
  const id = `blason${idBrut.replace(/:/g, "")}`;
  const cadre = option === "gros-plan" ? "25 25 50 50" : "0 0 100 100";

  return (
    <svg
      className="art"
      viewBox={cadre}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <radialGradient id={id} gradientUnits="userSpaceOnUse" cx="30" cy="22" r="85">
          <stop offset="0" stopColor={clair} />
          <stop offset="1" stopColor={fond} />
        </radialGradient>
      </defs>
      <rect width="100" height="100" fill={`url(#${id})`} />
      <Blason forme={forme} t={trace} f={`url(#${id})`} />
    </svg>
  );
});
