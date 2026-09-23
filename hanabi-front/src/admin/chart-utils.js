/** Mesure et mise en forme des graphiques. Separe de `charts.jsx`, qui
 *  n'exporte ainsi que des composants (rechargement a chaud de Vite). */
import { useLayoutEffect, useRef, useState } from "react";

import { CHART, SEQUENTIAL } from "./palette.js";

/** Largeur reelle du conteneur : on dessine en pixels plutot que d'etirer un
 *  `viewBox`, qui deformerait traits et libelles. */
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

    // Mesure immediate : la premiere notification de ResizeObserver peut
    // arriver tard, voire jamais sur une page non composee.
    mesurer();

    let observer;
    if (typeof ResizeObserver === "function") {
      observer = new ResizeObserver(mesurer);
      observer.observe(node);
    }
    window.addEventListener("resize", mesurer);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", mesurer);
    };
  }, []);

  return [ref, width];
}

/** Graduations rondes (0, 250, 500) dont la derniere couvre toujours le
 *  maximum : c'est elle qui fixe le haut de l'echelle. */
export function niceTicks(max, count = 4) {
  if (max <= 0) return [0];
  const brut = max / count;
  const magnitude = 10 ** Math.floor(Math.log10(brut));
  const pas = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((p) => p >= brut) || magnitude * 10;

  // Par multiplication : additionner un pas comme 0,025 accumule l'erreur
  // binaire et affiche « 99,99999 ».
  const intervalles = Math.ceil(max / pas);
  return Array.from({ length: intervalles + 1 }, (_, i) => i * pas);
}

const compact = new Intl.NumberFormat("fr-FR", { notation: "compact", maximumFractionDigits: 1 });

/** 12,9 k plutot que 12 934. */
export const axisNumber = (v) => (Math.abs(v) >= 1000 ? compact.format(v) : String(Math.round(v)));

/** Idem pour des centimes, rendus en euros. */
export const axisEuro = (v) =>
  Math.abs(v) >= 100000 ? `${compact.format(v / 100)} €` : `${Math.round(v / 100)} €`;

/** Trace lisse passant par tous les points sans jamais les depasser. */
export function smoothPath(points) {
  if (points.length < 2) {
    return points.length ? `M${points[0].x},${points[0].y}` : "";
  }

  const n = points.length;
  const pentes = [];
  for (let i = 0; i < n - 1; i++) {
    const dx = points[i + 1].x - points[i].x || 1;
    pentes.push((points[i + 1].y - points[i].y) / dx);
  }

  const m = [pentes[0]];
  for (let i = 1; i < n - 1; i++) {
    // Un changement de sens force une tangente plate
    m.push(pentes[i - 1] * pentes[i] <= 0 ? 0 : (pentes[i - 1] + pentes[i]) / 2);
  }
  m.push(pentes[n - 2]);

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

/** Rang de la rampe sequentielle pour une valeur, -1 sans donnee. */
export function heatStep(value, max) {
  if (!max || value <= 0) return -1;
  return Math.min(SEQUENTIAL.length - 1, Math.floor((value / max) * SEQUENTIAL.length));
}

/** Pas de la rampe sequentielle correspondant a une valeur. */
export function heatColor(value, max) {
  const rang = heatStep(value, max);
  return rang < 0 ? CHART.empty : SEQUENTIAL[rang];
}
