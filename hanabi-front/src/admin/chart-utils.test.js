/** Outils de mesure des graphiques.
 *
 * `smoothPath` merite mieux qu'un test de valeurs figees. Son commentaire
 * annonce une garantie - la courbe ne depasse jamais les points mesures - et
 * c'est cette garantie qu'on verifie, en echantillonnant les courbes de Bezier
 * produites. Un test qui comparerait la chaine `d` a une chaine attendue
 * casserait au moindre changement d'arrondi tout en laissant passer un vrai
 * depassement : il verifierait la sortie sans verifier la promesse.
 */
import { describe, it, expect } from "vitest";

import { niceTicks, axisNumber, axisEuro, smoothPath, heatColor } from "./chart-utils.js";
import { CHART, SEQUENTIAL } from "./palette.js";

/** Ordonnee d'une courbe de Bezier cubique au parametre t. */
const bezierY = (p0, p1, p2, p3, t) => {
  const u = 1 - t;
  return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
};

/**
 * Rejoue le trace et renvoie, pour chaque segment, les ordonnees echantillonnees.
 * On lit la chaine `d` plutot que de refaire le calcul : c'est bien la sortie
 * reelle du module qui est mise a l'epreuve.
 */
function echantillonner(d, pas = 40) {
  const nombres = (s) => s.trim().split(",").map(Number);
  const segments = d.split(" C").slice(1);
  const depart = nombres(d.slice(1).split(" C")[0]);

  const sorties = [];
  let courant = depart;
  for (const segment of segments) {
    const [c1, c2, fin] = segment.trim().split(" ").map(nombres);
    const ys = [];
    for (let i = 0; i <= pas; i++) ys.push(bezierY(courant[1], c1[1], c2[1], fin[1], i / pas));
    sorties.push({ debut: courant, fin, ys });
    courant = fin;
  }
  return sorties;
}

const enPoints = (valeurs) => valeurs.map((y, i) => ({ x: i * 10, y }));

describe("niceTicks", () => {
  it("produit des graduations rondes", () => {
    expect(niceTicks(1000)).toEqual([0, 250, 500, 750, 1000]);
  });

  it("part toujours de zero", () => {
    for (const max of [1, 7, 93, 1234, 999999]) {
      expect(niceTicks(max)[0]).toBe(0);
    }
  });

  it("couvre la valeur maximale, sans quoi une barre sortirait du cadre", () => {
    for (const max of [1, 7, 93, 237, 1234, 88888]) {
      const ticks = niceTicks(max);
      expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(max);
    }
  });

  it("reste strictement croissante et d'un pas constant", () => {
    for (const max of [3, 47, 512, 9600]) {
      const ticks = niceTicks(max);
      const pas = ticks[1] - ticks[0];
      for (let i = 1; i < ticks.length; i++) {
        expect(ticks[i] - ticks[i - 1]).toBeCloseTo(pas, 6);
      }
    }
  });

  it("degenere proprement sur une serie vide ou nulle", () => {
    // Un axe sans donnee doit afficher un zero, pas une boucle infinie.
    expect(niceTicks(0)).toEqual([0]);
    expect(niceTicks(-5)).toEqual([0]);
  });
});

describe("axisNumber", () => {
  it("laisse les petites valeurs entieres", () => {
    expect(axisNumber(0)).toBe("0");
    expect(axisNumber(999)).toBe("999");
  });

  it("abrege a partir du millier", () => {
    expect(axisNumber(12934)).toMatch(/12,9/);
  });
});

describe("axisEuro", () => {
  it("convertit les centimes en euros", () => {
    expect(axisEuro(1000)).toBe("10 €");
  });

  it("abrege les gros montants", () => {
    expect(axisEuro(1234500)).toMatch(/€/);
    expect(axisEuro(1234500)).not.toMatch(/12345/);
  });
});

describe("smoothPath", () => {
  it("ne trace rien sans point", () => {
    expect(smoothPath([])).toBe("");
  });

  it("place un simple deplacement pour un point isole", () => {
    expect(smoothPath([{ x: 5, y: 9 }])).toBe("M5,9");
  });

  it("relie tous les points fournis", () => {
    const points = enPoints([10, 40, 20, 60]);
    const segments = echantillonner(smoothPath(points));
    expect(segments).toHaveLength(points.length - 1);
    segments.forEach((s, i) => {
      expect(s.fin[0]).toBeCloseTo(points[i + 1].x, 6);
      expect(s.fin[1]).toBeCloseTo(points[i + 1].y, 6);
    });
  });

  it("NE DEPASSE JAMAIS les points mesures", () => {
    // La promesse du module : entre deux mois a 0 et 100, la courbe ne doit pas
    // passer par 110. C'est ce qui distingue une spline monotone d'une spline
    // ordinaire, et c'est la seule raison d'avoir implemente Fritsch-Carlson.
    const series = [
      [0, 100, 0, 100, 0],
      [10, 40, 20, 60, 15],
      [5, 5, 5, 5],
      [0, 1, 100, 101],
      [100, 0, 100, 0],
      [3, 3, 90, 3, 3],
      [0, 0, 0, 250, 0, 0],
    ];

    for (const valeurs of series) {
      const points = enPoints(valeurs);
      for (const segment of echantillonner(smoothPath(points))) {
        const bas = Math.min(segment.debut[1], segment.fin[1]);
        const haut = Math.max(segment.debut[1], segment.fin[1]);
        for (const y of segment.ys) {
          // Tolerance de flottant seulement, pas de marge de complaisance.
          expect(y).toBeGreaterThanOrEqual(bas - 1e-9);
          expect(y).toBeLessThanOrEqual(haut + 1e-9);
        }
      }
    }
  });

  it("reste monotone sur une serie croissante", () => {
    const points = enPoints([0, 5, 20, 21, 90, 200]);
    for (const segment of echantillonner(smoothPath(points))) {
      for (let i = 1; i < segment.ys.length; i++) {
        expect(segment.ys[i]).toBeGreaterThanOrEqual(segment.ys[i - 1] - 1e-9);
      }
    }
  });

  it("trace un plateau parfaitement plat", () => {
    // Trois mois identiques ne doivent pas produire d'ondulation : elle ferait
    // lire une variation qui n'existe pas.
    for (const segment of echantillonner(smoothPath(enPoints([42, 42, 42, 42])))) {
      for (const y of segment.ys) expect(y).toBeCloseTo(42, 9);
    }
  });

  it("ne produit aucune coordonnee non finie", () => {
    // Deux points de meme abscisse divisaient par zero : le garde-fou `|| 1`
    // dans le calcul des pentes existe pour ca.
    const colles = [
      { x: 0, y: 10 },
      { x: 0, y: 50 },
      { x: 10, y: 30 },
    ];
    const d = smoothPath(colles);
    expect(d).not.toMatch(/NaN|Infinity/);
  });
});

describe("heatColor", () => {
  it("rend la teinte vide pour une case sans donnee", () => {
    expect(heatColor(0, 100)).toBe(CHART.empty);
    expect(heatColor(5, 0)).toBe(CHART.empty);
  });

  it("ne sort jamais de la rampe, valeur maximale comprise", () => {
    // `Math.floor((value / max) * length)` vaut exactement `length` quand la
    // valeur egale le maximum : sans le plafonnement, la case la plus chaude du
    // graphique serait `undefined`.
    for (const v of [1, 25, 50, 99, 100]) {
      expect(SEQUENTIAL).toContain(heatColor(v, 100));
    }
    expect(heatColor(100, 100)).toBe(SEQUENTIAL[SEQUENTIAL.length - 1]);
  });

  it("est croissante : plus la valeur monte, plus le pas avance", () => {
    let precedent = -1;
    for (let v = 1; v <= 100; v++) {
      const rang = SEQUENTIAL.indexOf(heatColor(v, 100));
      expect(rang).toBeGreaterThanOrEqual(precedent);
      precedent = rang;
    }
  });
});
