import { useEffect } from "react";

const REVEAL_ZONE_PX = 80;

/**
 * Retracte l'en-tete au defilement vers le bas, le revele vers le haut.
 *
 * Ecriture IMPERATIVE, directement sur le noeud passe en ref, sans etat React.
 * C'est le point decisif pour la fluidite du defilement.
 *
 * La version precedente passait par `useState`. Or cet etat vivait dans la
 * racine de l'application : chaque changement - a chaque inversion de sens -
 * re-rendait tout l'arbre, mille cinq cents noeuds, en plein defilement. Sur un
 * va-et-vient rapide a la molette, ces re-rendus s'enchainaient plus vite que
 * le navigateur ne pouvait peindre, et la cadence tombait sous les soixante
 * images par seconde - exactement le symptome ressenti. Le meme piege qu'un
 * effet de survol branche sur `useState`, que `useTilt` evite deja pour cette
 * raison, et que `ScrollProgress` evite aussi en ecrivant sa variable CSS a la
 * main.
 *
 * On ne touche le DOM que lorsqu'un des deux etats change reellement : la
 * plupart des images de defilement ne font donc rien du tout, et le seul cout
 * restant est la transformation de l'en-tete, composee par le GPU.
 *
 * @param {import("react").RefObject<HTMLElement>} ref l'en-tete a piloter
 */
export function useHideOnScroll(ref) {
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;

    let lastY = window.scrollY;
    let ticking = false;
    let estCache = false;

    const apply = () => {
      ticking = false;
      const y = window.scrollY;
      // Pres du haut, l'en-tete reste toujours visible.
      const cache = y > REVEAL_ZONE_PX && y > lastY;
      if (cache !== estCache) {
        node.classList.toggle("hidden", cache);
        estCache = cache;
      }
      lastY = y;
    };

    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(apply);
    };

    // La page peut deja etre defilee au montage : rechargement au milieu d'une
    // page, retour arriere du navigateur, ancre dans l'URL.
    apply();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [ref]);
}
