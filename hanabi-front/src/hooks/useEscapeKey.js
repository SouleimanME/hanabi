import { useEffect, useRef } from "react";

/** Appelle `onEscape` a chaque appui sur la touche Echap. */
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
