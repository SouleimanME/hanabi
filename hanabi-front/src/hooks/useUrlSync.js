import { useEffect, useRef } from "react";
import { parsePath, pathFor } from "../lib/routes.js";

/**
 * Maintient l'URL et l'ecran affiche en accord, dans les deux sens.
 *
 * Trois responsabilites, volontairement reunies : elles partagent un garde-fou
 * commun et les separer ferait boucler la synchronisation.
 *
 *   1. Au chargement, l'URL fait foi - c'est ce qui rend une fiche produit
 *      partageable et memorisable dans les favoris.
 *   2. Quand l'ecran change, l'URL est mise a jour (pushState).
 *   3. Aux boutons Retour et Suivant, l'URL fait foi de nouveau (popstate).
 *
 * Le garde-fou est `applyingUrl` : sans lui, appliquer une URL modifierait
 * l'etat, ce qui declencherait l'ecriture d'une nouvelle entree d'historique,
 * qui redeclencherait l'application... Le drapeau coupe la boucle en marquant
 * les changements d'etat qui viennent deja de l'URL.
 *
 * @param {{
 *   view: string,
 *   setView: (v: string) => void,
 *   activeProduct: {id: number}|null,
 *   openProductById: (id: number) => void,
 * }} params
 */
export function useUrlSync({ view, setView, activeProduct, openProductById }) {
  const applyingUrl = useRef(false);
  const ready = useRef(false);

  // Les fonctions changent a chaque rendu ; on lit toujours la derniere version
  // sans reabonner l'ecouteur popstate pour autant.
  const latest = useRef({ setView, openProductById });
  latest.current = { setView, openProductById };

  const applyPath = (pathname) => {
    const { view: nextView, productId } = parsePath(pathname);
    applyingUrl.current = true;
    if (nextView === "product" && productId) {
      latest.current.openProductById(productId);
    } else {
      latest.current.setView(nextView);
    }
  };

  // 1. Etat initial : l'URL fait foi.
  useEffect(() => {
    // Volontairement une seule fois : c'est l'amorcage. `applyPath` ne lit que
    // des refs, donc rien a declarer en dependance.
    applyPath(window.location.pathname);
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
      window.history.pushState(null, "", path);
    }
  }, [view, activeProduct]);

  // 3. Boutons Retour et Suivant du navigateur.
  useEffect(() => {
    const onPopState = () => applyPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
}
