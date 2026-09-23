import { useEffect, useRef } from "react";

/** Elements qui peuvent recevoir le focus au clavier. */
const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

/** Enferme le focus clavier dans une fenetre modale.
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

    // Le premier champ recoit le focus a l'ouverture : la saisie commence sans avoir a viser a la souris
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
