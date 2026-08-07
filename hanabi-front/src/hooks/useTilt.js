import { useCallback, useEffect, useRef } from "react";
import { useReducedMotion } from "./useReducedMotion.js";

/**
 * Inclinaison 3D d'une carte qui suit le curseur, plus un reflet mobile.
 *
 * On ecrit directement dans le style de l'element via des variables CSS
 * (`--rx`, `--ry`, `--mx`, `--my`) plutot que par l'etat React : bouger la
 * souris declenche des dizaines d'evenements par seconde, un re-rendu a chaque
 * fois saccaderait. Le calcul reste hors du cycle de rendu, seul le compositeur
 * du navigateur travaille.
 *
 * Rendu inerte si l'utilisateur a demande a limiter les animations.
 *
 * @param {{max?: number}} [opts] inclinaison maximale en degres
 * @returns {{ref, onMouseEnter, onMouseMove, onMouseLeave}} a etaler sur la cible
 */
export function useTilt({ max = 9 } = {}) {
  const ref = useRef(null);
  const reduced = useReducedMotion();
  const pointer = useRef(null);
  const frame = useRef(0);
  // Dimensions et position de la carte, mesurees une fois a l'entree du curseur
  // et conservees pour toute la duree du survol.
  const rect = useRef(null);

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  /** Une souris emet bien plus d'evenements qu'il n'y a d'images a l'ecran -
   *  jusqu'a mille par seconde sur du materiel de jeu. On ne garde que la
   *  derniere position et on n'ecrit qu'une fois par image.
   *
   *  La carte n'est PAS remesuree ici. `getBoundingClientRect` force un recalcul
   *  de mise en page, et le declencher a chaque image pendant un balayage rapide
   *  du catalogue faisait ceder la fluidite : le recalcul lisait une geometrie
   *  que les transitions des cartes voisines venaient d'invalider, le cas d'ecole
   *  du « layout thrashing ». La carte ne bouge pas pendant qu'on la survole, sa
   *  geometrie mesuree a l'entree reste donc valable jusqu'a la sortie. */
  const apply = useCallback(() => {
    frame.current = 0;
    const node = ref.current;
    const position = pointer.current;
    const r = rect.current;
    if (!node || !position || !r) return;
    const px = (position.x - r.left) / r.width; // 0 → 1
    const py = (position.y - r.top) / r.height;
    node.style.setProperty("--ry", `${(px - 0.5) * 2 * max}deg`);
    node.style.setProperty("--rx", `${(0.5 - py) * 2 * max}deg`);
    // En pourcentage, pour ce qui s'en sert comme point d'origine.
    node.style.setProperty("--mx", `${px * 100}%`);
    node.style.setProperty("--my", `${py * 100}%`);
    // En pixels, pour ce qui se deplace par `transform`. Deplacer un element
    // compose ne coute rien ; deplacer la position d'un degrade repeint.
    node.style.setProperty("--sx", `${Math.round(position.x - r.left)}px`);
    node.style.setProperty("--sy", `${Math.round(position.y - r.top)}px`);
  }, [max]);

  // La seule mesure de la carte a lieu ici, une fois par survol.
  const onMouseEnter = useCallback(() => {
    if (reduced) return;
    const node = ref.current;
    if (node) rect.current = node.getBoundingClientRect();
  }, [reduced]);

  const onMouseMove = useCallback(
    (e) => {
      if (reduced) return;
      // Filet de securite : un survol demarre par un clavier ou un focus
      // programme peut declencher un mouvement sans entree prealable.
      if (!rect.current && ref.current) rect.current = ref.current.getBoundingClientRect();
      pointer.current = { x: e.clientX, y: e.clientY };
      if (!frame.current) frame.current = requestAnimationFrame(apply);
    },
    [apply, reduced],
  );

  const onMouseLeave = useCallback(() => {
    cancelAnimationFrame(frame.current);
    frame.current = 0;
    pointer.current = null;
    const r = rect.current;
    rect.current = null;
    const node = ref.current;
    if (!node) return;
    node.style.setProperty("--ry", "0deg");
    node.style.setProperty("--rx", "0deg");
    node.style.setProperty("--mx", "50%");
    node.style.setProperty("--my", "50%");
    if (r) {
      node.style.setProperty("--sx", `${Math.round(r.width / 2)}px`);
      node.style.setProperty("--sy", `${Math.round(r.height / 2)}px`);
    }
  }, []);

  return { ref, onMouseEnter, onMouseMove, onMouseLeave };
}
