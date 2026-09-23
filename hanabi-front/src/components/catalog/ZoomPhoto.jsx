/** Zoom libre sur la vue principale d'une fiche : clic ou tape (agrandit là où
 *  l'on vise, puis revient), molette sous le curseur, pincement au doigt,
 *  Entrée ou Espace, touches + − 0 et flèches. Le cadrage passe par
 *  `transform`, posé dans requestAnimationFrame sans re-rendu React : aucune
 *  trame perdue pendant le geste. */
import { useCallback, useEffect, useRef } from "react";

const MAX = 4;
const AU_CLIC = 2.5;
// Au-delà, le geste est un déplacement et non un clic
const TOLERANCE_CLIC_PX = 6;

const borner = (v, min, max) => Math.min(max, Math.max(min, v));

export function ZoomPhoto({ children, libelle, aide }) {
  const cadre = useRef(null);
  const plan = useRef(null);
  const etat = useRef({ s: 1, x: 0, y: 0 });
  const trame = useRef(0);
  const doigts = useRef(new Map());
  const pince = useRef(null);
  const geste = useRef(null);
  const grandeTaille = useRef(false);

  const peindre = useCallback(() => {
    trame.current = 0;
    const { s, x, y } = etat.current;
    plan.current.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${s})`;
    cadre.current.dataset.zoom = s > 1 ? "oui" : "non";
    cadre.current.setAttribute("aria-pressed", s > 1 ? "true" : "false");
  }, []);

  const appliquer = useCallback(
    (s, x, y) => {
      const { width: l, height: h } = cadre.current.getBoundingClientRect();
      s = borner(s, 1, MAX);
      // L'image couvre toujours son cadre : pas de bord vide en déplaçant
      etat.current = { s, x: borner(x, l - l * s, 0), y: borner(y, h - h * s, 0) };
      if (s > 1 && !grandeTaille.current) {
        // Agrandie, la photo demande au navigateur une version à sa mesure
        const img = plan.current.querySelector("img");
        if (img) img.sizes = `${Math.ceil(l * MAX)}px`;
        grandeTaille.current = true;
      }
      if (!trame.current) trame.current = requestAnimationFrame(peindre);
    },
    [peindre],
  );

  /** Zoome d'un facteur autour d'un point du cadre, qui reste sous le curseur. */
  const zoomerEn = useCallback(
    (facteur, px, py) => {
      const { s, x, y } = etat.current;
      const s2 = borner(s * facteur, 1, MAX);
      const k = s2 / s;
      appliquer(s2, px - (px - x) * k, py - (py - y) * k);
    },
    [appliquer],
  );

  /** Clic, tape, Entrée : agrandit au point visé, ou revient au plein cadre. */
  const basculer = useCallback(
    (px, py) => {
      if (etat.current.s > 1) appliquer(1, 0, 0);
      else zoomerEn(AU_CLIC, px, py);
    },
    [appliquer, zoomerEn],
  );

  const point = (e) => {
    const r = cadre.current.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };

  // La molette a besoin d'un écouteur non passif pour empêcher le défilement
  useEffect(() => {
    const noeud = cadre.current;
    const surMolette = (e) => {
      // Le cadre garde la molette, même en butée : la page ne bouge pas sous la photo
      e.preventDefault();
      zoomerEn(Math.exp(-e.deltaY * 0.0015), ...point(e));
    };
    noeud.addEventListener("wheel", surMolette, { passive: false });
    return () => {
      noeud.removeEventListener("wheel", surMolette);
      cancelAnimationFrame(trame.current);
    };
  }, [zoomerEn]);

  const surAppui = (e) => {
    const p = point(e);
    doigts.current.set(e.pointerId, p);
    // Un geste commencé à un doigt peut encore devenir un clic
    geste.current = doigts.current.size === 1 ? { depart: p, clic: true } : null;
    if (doigts.current.size === 2) {
      const [a, b] = [...doigts.current.values()];
      pince.current = { d: Math.hypot(a[0] - b[0], a[1] - b[1]) };
    }
    if (etat.current.s > 1 || doigts.current.size === 2) {
      cadre.current.setPointerCapture?.(e.pointerId);
    }
  };

  const surDeplacement = (e) => {
    const avant = doigts.current.get(e.pointerId);
    if (!avant) return;
    const apres = point(e);
    doigts.current.set(e.pointerId, apres);
    const g = geste.current;
    if (g && Math.hypot(apres[0] - g.depart[0], apres[1] - g.depart[1]) > TOLERANCE_CLIC_PX) {
      g.clic = false;
    }

    if (doigts.current.size === 2 && pince.current) {
      const [a, b] = [...doigts.current.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      zoomerEn(d / pince.current.d, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2);
      pince.current.d = d;
    } else if (doigts.current.size === 1 && etat.current.s > 1) {
      const { s, x, y } = etat.current;
      appliquer(s, x + apres[0] - avant[0], y + apres[1] - avant[1]);
    }
  };

  const surRelache = (e) => {
    const [px, py] = point(e);
    const etaitSeul = doigts.current.size === 1;
    doigts.current.delete(e.pointerId);
    if (doigts.current.size < 2) pince.current = null;
    // Bouton principal seulement : un clic droit garde son menu
    if (etaitSeul && geste.current?.clic && e.button === 0 && e.type === "pointerup") {
      basculer(px, py);
    }
    geste.current = null;
  };

  const surTouche = (e) => {
    const { width: l, height: h } = cadre.current.getBoundingClientRect();
    const { s, x, y } = etat.current;
    const pas = 40;
    const actions = {
      Enter: () => basculer(l / 2, h / 2),
      " ": () => basculer(l / 2, h / 2),
      "+": () => zoomerEn(1.5, l / 2, h / 2),
      "=": () => zoomerEn(1.5, l / 2, h / 2),
      "-": () => zoomerEn(1 / 1.5, l / 2, h / 2),
      0: () => appliquer(1, 0, 0),
      ArrowLeft: () => appliquer(s, x + pas, y),
      ArrowRight: () => appliquer(s, x - pas, y),
      ArrowUp: () => appliquer(s, x, y + pas),
      ArrowDown: () => appliquer(s, x, y - pas),
    };
    const action = actions[e.key];
    // Au plein cadre, les flèches gardent leur rôle habituel
    if (!action || (e.key.startsWith("Arrow") && s <= 1)) return;
    e.preventDefault();
    action();
  };

  return (
    <div
      ref={cadre}
      className="zoom"
      data-zoom="non"
      tabIndex={0}
      role="button"
      aria-pressed="false"
      aria-label={libelle}
      aria-describedby={aide}
      onPointerDown={surAppui}
      onPointerMove={surDeplacement}
      onPointerUp={surRelache}
      onPointerCancel={surRelache}
      onKeyDown={surTouche}
    >
      <div ref={plan} className="zoom-plan">
        {children}
      </div>
    </div>
  );
}
