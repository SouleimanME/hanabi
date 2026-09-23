/** Fonction d'identité fixe qui appelle toujours la dernière version reçue.
 *  Transmise à une liste mémoïsée, elle ne la fait pas re-rendre à chaque
 *  changement d'état qu'elle lit. */
import { useCallback, useLayoutEffect, useRef } from "react";

export function useFonctionStable(fonction) {
  const derniere = useRef(fonction);
  useLayoutEffect(() => {
    derniere.current = fonction;
  });
  return useCallback((...args) => derniere.current(...args), []);
}
