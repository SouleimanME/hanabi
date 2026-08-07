import { useState, useRef, useEffect, useCallback } from "react";

const VISIBLE_MS = 2400;

/**
 * File d'attente a un seul message pour les notifications breves.
 *
 * Un nouveau message remplace le precedent et relance le minuteur : deux
 * ajouts au panier rapproches n'empilent pas deux toasts.
 */
export function useToast() {
  const [message, setMessage] = useState(null);
  const timer = useRef(null);

  const show = useCallback((text) => {
    setMessage(text);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(null), VISIBLE_MS);
  }, []);

  // Sans ce nettoyage, un demontage pendant l'affichage laisserait un
  // setState sur un composant demonte.
  useEffect(() => () => clearTimeout(timer.current), []);

  return { message, show };
}
