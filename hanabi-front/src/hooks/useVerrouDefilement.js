import { useEffect } from "react";

/** Fige le défilement de la page tant qu'une feuille ou une fenêtre est ouverte.
 *
 * La molette sur le voile faisait défiler la page derrière. La largeur de la
 * barre qui disparaît est rendue en marge, pour que rien ne saute de côté.
 */
export function useVerrouDefilement(actif) {
  useEffect(() => {
    if (!actif) return undefined;
    const racine = document.documentElement;
    const barre = window.innerWidth - racine.clientWidth;
    racine.style.setProperty("--barre-defilement", `${barre}px`);
    racine.dataset.verrou = "";
    return () => {
      delete racine.dataset.verrou;
      racine.style.removeProperty("--barre-defilement");
    };
  }, [actif]);
}
