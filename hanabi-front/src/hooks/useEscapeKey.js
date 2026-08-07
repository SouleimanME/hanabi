import { useEffect, useRef } from "react";

/**
 * Appelle `onEscape` a chaque appui sur la touche Echap.
 *
 * Le gestionnaire est garde dans une ref : l'ecouteur n'est pose qu'une fois,
 * meme si l'appelant passe une fonction recreee a chaque rendu.
 */
export function useEscapeKey(onEscape) {
  const handler = useRef(onEscape);
  handler.current = onEscape;

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === "Escape") handler.current();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
