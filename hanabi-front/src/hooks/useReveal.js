import { useEffect, useState } from "react";

/**
 * Declenche l'apparition d'un element quand il entre dans le champ de vision.
 *
 * S'appuie sur IntersectionObserver plutot que sur un ecouteur de defilement :
 * le navigateur fait le calcul hors du fil principal, sans reflow a chaque
 * pixel parcouru.
 *
 * L'observation s'arrete des le premier passage : l'element ne doit pas
 * disparaitre puis reapparaitre quand on remonte la page.
 *
 * Le noeud est tenu dans un etat plutot que dans une ref, et la fonction
 * renvoyee s'utilise comme une ref de rappel (`ref={setNode}`). C'est ce qui
 * rend le hook fiable sur un element affiche conditionnellement : avec une
 * simple ref, l'effet ne s'executerait qu'au premier rendu - alors que le
 * noeud n'existe pas encore - et l'observateur ne serait jamais attache,
 * laissant l'element invisible pour toujours.
 *
 * @param {{threshold?: number, rootMargin?: string, disabled?: boolean}} options
 * @returns {[(node: Element|null) => void, boolean]} la ref de rappel, et l'etat "visible"
 */
export function useReveal({
  threshold = 0.15,
  rootMargin = "0px 0px -80px 0px",
  disabled = false,
} = {}) {
  const [node, setNode] = useState(null);
  const [visible, setVisible] = useState(disabled);

  useEffect(() => {
    if (disabled) {
      setVisible(true);
      return;
    }
    if (!node) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [node, threshold, rootMargin, disabled]);

  return [setNode, visible];
}
