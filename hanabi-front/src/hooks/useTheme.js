import { useCallback, useEffect, useState } from "react";
import { storage } from "../lib/storage.js";

/** Cle de stockage du choix explicite.
 *
 * Volontairement differente de l'ancienne cle « theme » : celle-ci recevait la
 * valeur par defaut des le premier rendu, sans que personne ait rien choisi. La
 * reprendre reviendrait a considerer tout le monde comme ayant deja tranche, et
 * le reglage du systeme ne serait jamais consulte. */
const KEY = "themeChoice";

const systemTheme = () =>
  window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";

/**
 * Theme clair ou sombre, aligne par defaut sur le reglage du systeme.
 *
 * Trois comportements, dans cet ordre de priorite :
 *
 *   1. Tant que personne n'a touche au bouton, le site suit le systeme - et
 *      continue de le suivre en direct. Basculer son telephone en mode sombre
 *      le soir bascule l'onglet ouvert, sans rechargement.
 *   2. Des qu'on utilise le bouton, ce choix est memorise et prime : quelqu'un
 *      qui veut le site en clair sur un systeme sombre doit pouvoir l'obtenir.
 *   3. Le choix survit au rechargement.
 *
 * @returns {[("light"|"dark"), () => void, boolean]} theme, bascule, et vrai
 *   si l'on suit encore le systeme
 */
export function useTheme() {
  // `null` signifie « aucun choix explicite », et non « clair ».
  const [choice, setChoice] = useState(() => storage.get(KEY, null));
  const [system, setSystem] = useState(systemTheme);

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return;
    const onChange = (e) => setSystem(e.matches ? "dark" : "light");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const theme = choice ?? system;

  // Repercute le theme sur <html>, hors de l'arbre React.
  //
  // Deux effets que le conteneur de l'application ne peut pas produire :
  //   - le fond de <html> teinte ce que le navigateur peint autour de la page,
  //     ce qui evite le cadre blanc autour d'un site sombre sur telephone ;
  //   - `theme-color` colore la barre d'adresse. Les balises figees dans
  //     index.html suivent le reglage du systeme, alors que le visiteur peut
  //     avoir choisi l'inverse avec le bouton : on aligne donc sur le theme
  //     reellement affiche.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;

    const couleur = theme === "dark" ? "#15130f" : "#f4f0e6";
    for (const balise of document.querySelectorAll('meta[name="theme-color"]')) {
      // Les variantes `media` reprendraient le dessus : on les neutralise.
      balise.removeAttribute("media");
      balise.setAttribute("content", couleur);
    }
  }, [theme]);

  const toggle = useCallback(() => {
    const next = theme === "dark" ? "light" : "dark";
    storage.set(KEY, next);
    setChoice(next);
  }, [theme]);

  return [theme, toggle, choice === null];
}
