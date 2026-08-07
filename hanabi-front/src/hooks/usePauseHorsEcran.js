import { useEffect, useRef } from "react";

/**
 * Fige les animations CSS d'un bloc tant qu'il n'est pas a l'ecran.
 *
 * `Fireworks` applique deja ce principe a sa boucle de dessin, et son
 * commentaire le formule mieux que je ne le ferais : continuer a dessiner un
 * canevas qu'on a depasse en defilant coute la meme chose que de le regarder.
 * La phrase vaut mot pour mot pour une animation CSS, qui n'avait pourtant
 * aucune protection equivalente - les cinq animations `infinite` du site
 * tournaient en permanence, y compris plusieurs ecrans plus haut.
 *
 * Le repos est marque par un attribut plutot que par une classe : il decrit un
 * etat, pas une intention de style, et il se lit dans l'inspecteur sans avoir a
 * deviner ce qu'une classe voulait dire.
 *
 * Le navigateur reprend l'animation la ou elle s'etait arretee : `paused` gele
 * la progression, il ne la remet pas a zero. Un halo surpris en cours
 * d'inspiration ne saute donc pas en revenant.
 *
 * @returns {import("react").RefObject} a poser sur le bloc a surveiller
 */
export function usePauseHorsEcran() {
  const ref = useRef(null);

  useEffect(() => {
    const noeud = ref.current;
    if (!noeud) return undefined;

    // Sans IntersectionObserver - navigateur ancien, environnement de test -
    // on ne fige rien. Le site reste correct, simplement moins econome : c'est
    // une optimisation, jamais une condition de fonctionnement.
    if (typeof IntersectionObserver === "undefined") return undefined;

    const observateur = new IntersectionObserver(([entree]) => {
      noeud.toggleAttribute("data-fige", !entree.isIntersecting);
    });
    observateur.observe(noeud);

    return () => observateur.disconnect();
  }, []);

  return ref;
}
