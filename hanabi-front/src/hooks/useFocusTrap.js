import { useEffect, useRef } from "react";

/** Elements qui peuvent recevoir le focus au clavier.
 *
 * `:not([disabled])` et `tabindex="-1"` sont exclus : un bouton desactive ou
 * volontairement retire du parcours ne doit pas capter la tabulation. C'est ce
 * qui ecarte aussi le champ piege anti-robots (voir useAntiBot). */
const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

/**
 * Enferme le focus clavier dans une fenetre modale.
 *
 * Sans cela, la tabulation sort de la fenetre et continue de parcourir la page
 * situee derriere : une personne naviguant au clavier ou au lecteur d'ecran se
 * retrouve a remplir un formulaire qu'elle ne voit plus, sous un voile qui lui
 * cache tout. C'est le comportement attendu de `aria-modal="true"`, que
 * l'attribut declare mais n'implemente pas - il informe la technologie
 * d'assistance, il ne contraint pas le navigateur.
 *
 * Le focus precedent est rendu a la fermeture, pour que la navigation reprenne
 * ou elle s'etait arretee et non en haut de page.
 *
 * @param {boolean} [active] permet de conditionner le piege
 * @returns {React.RefObject} ref a poser sur le conteneur de la fenetre
 */
export function useFocusTrap(active = true) {
  const ref = useRef(null);

  useEffect(() => {
    if (!active) return;
    const node = ref.current;
    if (!node) return;

    const previous = document.activeElement;

    const focusable = () => [...node.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent);

    // Le premier champ recoit le focus a l'ouverture : la saisie commence sans
    // avoir a viser a la souris. A defaut, la fenetre elle-meme le prend, pour
    // que la touche Echap et le lecteur d'ecran aient un point d'ancrage.
    const first = focusable()[0];
    if (first) first.focus();
    else {
      node.setAttribute("tabindex", "-1");
      node.focus();
    }

    const onKeyDown = (e) => {
      if (e.key !== "Tab") return;
      const items = focusable();
      if (items.length === 0) return;

      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      const current = document.activeElement;

      // Aux extremites, on boucle plutot que de laisser sortir.
      if (e.shiftKey && (current === firstItem || !node.contains(current))) {
        e.preventDefault();
        lastItem.focus();
      } else if (!e.shiftKey && current === lastItem) {
        e.preventDefault();
        firstItem.focus();
      }
    };

    node.addEventListener("keydown", onKeyDown);
    return () => {
      node.removeEventListener("keydown", onKeyDown);
      // `focus` peut avoir disparu du document entre-temps.
      if (previous instanceof HTMLElement && document.contains(previous)) previous.focus();
    };
  }, [active]);

  return ref;
}
