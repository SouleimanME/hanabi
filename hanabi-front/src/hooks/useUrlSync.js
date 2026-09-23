import { useEffect, useRef } from "react";
import { parsePath, pathFor } from "../lib/routes.js";

/** Maintient l'URL et l'ecran affiche en accord, dans les deux sens.
 * `onJeton` et `onLien` recoivent ce qu'un lien de courriel porte dans sa requete.
 */
export function useUrlSync({ view, setView, activeProduct, openProductById, onJeton, onLien }) {
  const applyingUrl = useRef(false);
  const ready = useRef(false);

  // Les fonctions changent a chaque rendu ; on lit toujours la derniere version
  // sans reabonner l'ecouteur popstate pour autant.
  const latest = useRef({ setView, openProductById, onJeton, onLien });
  latest.current = { setView, openProductById, onJeton, onLien };

  const applyPath = (pathname, search) => {
    const { view: nextView, productId, jeton, lien } = parsePath(pathname, search);
    applyingUrl.current = true;
    if (nextView === "product" && productId) {
      latest.current.openProductById(productId);
    } else {
      // Transmis avant le changement d'ecran
      if (jeton) latest.current.onJeton?.(jeton);
      if (lien) latest.current.onLien?.(lien);
      latest.current.setView(nextView);
    }
  };

  // 1. Etat initial : l'URL fait foi.
  useEffect(() => {
    // Volontairement une seule fois : c'est l'amorcage. `applyPath` ne lit que
    // des refs, donc rien a declarer en dependance.
    applyPath(window.location.pathname, window.location.search);
    ready.current = true;
  }, []);

  // 2. L'ecran a change : on reflete l'URL.
  useEffect(() => {
    if (!ready.current) return;

    // Ce changement vient d'etre applique depuis l'URL : rien a reecrire.
    if (applyingUrl.current) {
      applyingUrl.current = false;
      return;
    }

    const path = pathFor(view, activeProduct);
    if (path !== window.location.pathname) {
      // `pathFor` ne produit jamais de requete
      window.history.pushState(null, "", path);
    }
  }, [view, activeProduct]);

  // 3. Boutons Retour et Suivant du navigateur.
  useEffect(() => {
    const onPopState = () => applyPath(window.location.pathname, window.location.search);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
}
