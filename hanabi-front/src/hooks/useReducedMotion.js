import { useState, useEffect } from "react";

/**
 * Indique si l'utilisateur a demande a limiter les animations.
 *
 * Toutes les animations du projet passent par ce hook. Une animation n'est pas
 * un detail cosmetique pour tout le monde : le mouvement peut declencher des
 * nausees ou des migraines chez les personnes sensibles au vestibulaire.
 * Quand le reglage systeme est actif, on ne degrade pas : on supprime.
 */
export function useReducedMotion() {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = (e) => setReduced(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
