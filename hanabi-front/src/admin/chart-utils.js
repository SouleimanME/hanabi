/** Outils de mesure et de mise en forme des graphiques.
 *
 * Separes de `charts.jsx` pour que ce dernier n'exporte que des composants : le
 * rechargement a chaud de Vite ne sait pas remplacer un module qui melange les
 * deux, et perd l'etat de la page a chaque modification.
 */
import { useLayoutEffect, useRef, useState } from "react";

import { CHART, SEQUENTIAL } from "./palette.js";

/** Largeur reelle du conteneur, suivie au redimensionnement.
 *
 * Sans cette mesure, il faudrait etirer un `viewBox` fixe, ce qui deforme les
 * traits et le texte : les libelles s'aplatissent et l'epaisseur d'un trait
 * change selon sa direction. On dessine donc en pixels reels.
 */
export function useMeasuredWidth(fallback = 640) {
  const ref = useRef(null);
  const [width, setWidth] = useState(fallback);

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return undefined;

    const mesurer = () => {
      const w = Math.round(node.getBoundingClientRect().width);
      if (w > 0) setWidth((precedent) => (Math.abs(precedent - w) > 1 ? w : precedent));
    };

    // Mesure immediate. `ResizeObserver` seul ne suffit pas : selon le moteur de
    // rendu, sa premiere notification arrive tard, voire jamais quand la page
    // n'est pas composee - le graphique resterait alors a sa largeur de repli et
    // deborderait de sa carte.
    mesurer();

    let observer;
    if (typeof ResizeObserver === "function") {
      observer = new ResizeObserver(mesurer);
      observer.observe(node);
    }
    // Filet supplementaire : le redimensionnement de la fenetre couvre le cas
    // ou l'observateur est indisponible.
    window.addEventListener("resize", mesurer);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", mesurer);
    };
  }, []);

  return [ref, width];
}

/** Graduations rondes : 0, 250, 500 plutot que 0, 237, 474.
 *
 * La derniere graduation COUVRE toujours le maximum, et c'est la seule chose
 * qui compte vraiment ici. La version precedente s'arretait au dernier multiple
 * du pas inferieur ou egal au maximum : pour un maximum de 93, elle rendait
 * [0, 25, 50, 75]. Or `charts.jsx` prend cette derniere valeur comme haut de
 * l'echelle, si bien que le point a 93 se tracait a 24 % de la hauteur du cadre
 * AU-DESSUS de celui-ci - hors du graphique, sur le titre. Le defaut ne se
 * voyait qu'en apparence, parce que les series de demonstration tombaient
 * souvent juste, mais il touchait tout maximum non multiple du pas, soit la
 * plupart des donnees reelles.
 *
 * On arrondit donc au multiple superieur. Le nombre d'intervalles ne depasse
 * jamais `count` pour autant : le pas est choisi superieur ou egal a
 * `max / count`, donc `ceil(max / pas) <= count`.
 */
export function niceTicks(max, count = 4) {
  if (max <= 0) return [0];
  const brut = max / count;
  const magnitude = 10 ** Math.floor(Math.log10(brut));
  const pas = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((p) => p >= brut) || magnitude * 10;

  // Graduations calculees par multiplication et non par addition repetee : un
  // pas comme 0,025 n'a pas de representation binaire exacte, et l'accumuler
  // dizaine de fois deplacait la derniere graduation d'un cheveu - assez pour
  // afficher « 99,99999 » sur un axe.
  const intervalles = Math.ceil(max / pas);
  return Array.from({ length: intervalles + 1 }, (_, i) => i * pas);
}

const compact = new Intl.NumberFormat("fr-FR", { notation: "compact", maximumFractionDigits: 1 });

/** Abrege pour un axe : 12,9 k plutot que 12 934. */
export const axisNumber = (v) => (Math.abs(v) >= 1000 ? compact.format(v) : String(Math.round(v)));

/** Idem pour des centimes, rendus en euros. */
export const axisEuro = (v) =>
  Math.abs(v) >= 100000 ? `${compact.format(v / 100)} €` : `${Math.round(v / 100)} €`;

/** Trace lisse passant par tous les points, sans jamais les depasser.
 *
 * Interpolation cubique monotone. Une spline ordinaire produit de belles
 * courbes mais depasse les points : entre deux mois a 0 et 100, elle passe par
 * 110 puis redescend, ce qui invente une valeur que les donnees ne contiennent
 * pas. La contrainte de monotonie interdit ce depassement - c'est la seule
 * forme de lissage acceptable sur une serie mesuree.
 *
 * `points` : [{ x, y }] deja convertis en coordonnees d'ecran.
 */
export function smoothPath(points) {
  if (points.length < 2) {
    return points.length ? `M${points[0].x},${points[0].y}` : "";
  }

  const n = points.length;
  // Pentes des segments, puis pente en chaque point.
  const pentes = [];
  for (let i = 0; i < n - 1; i++) {
    const dx = points[i + 1].x - points[i].x || 1;
    pentes.push((points[i + 1].y - points[i].y) / dx);
  }

  const m = [pentes[0]];
  for (let i = 1; i < n - 1; i++) {
    // Un changement de sens force une tangente plate : c'est ce qui empeche la
    // courbe de deborder au-dela d'un sommet ou d'un creux.
    m.push(pentes[i - 1] * pentes[i] <= 0 ? 0 : (pentes[i - 1] + pentes[i]) / 2);
  }
  m.push(pentes[n - 2]);

  // Limitation de Fritsch-Carlson : borne les tangentes pour garantir la
  // monotonie sur chaque intervalle.
  for (let i = 0; i < n - 1; i++) {
    if (pentes[i] === 0) {
      m[i] = 0;
      m[i + 1] = 0;
      continue;
    }
    const a = m[i] / pentes[i];
    const b = m[i + 1] / pentes[i];
    const s = a * a + b * b;
    if (s > 9) {
      const t = (3 / Math.sqrt(s)) * pentes[i];
      m[i] = t * a;
      m[i + 1] = t * b;
    }
  }

  let d = `M${points[0].x},${points[0].y}`;
  for (let i = 0; i < n - 1; i++) {
    const dx = points[i + 1].x - points[i].x;
    d += ` C${points[i].x + dx / 3},${points[i].y + (m[i] * dx) / 3}`;
    d += ` ${points[i + 1].x - dx / 3},${points[i + 1].y - (m[i + 1] * dx) / 3}`;
    d += ` ${points[i + 1].x},${points[i + 1].y}`;
  }
  return d;
}

/** Pas de la rampe sequentielle correspondant a une valeur. */
export function heatColor(value, max) {
  if (!max || value <= 0) return CHART.empty;
  const rang = Math.min(SEQUENTIAL.length - 1, Math.floor((value / max) * SEQUENTIAL.length));
  return SEQUENTIAL[rang];
}
