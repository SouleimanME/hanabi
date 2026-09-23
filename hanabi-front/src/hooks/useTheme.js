import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { storage } from "../lib/storage.js";

/** Cle du choix explicite. Absente, le site suit le systeme. */
const KEY = "themeChoice";

const systemTheme = () =>
  window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";

const COULEUR_BARRE = { light: "#efe7d6", dark: "#0a0605" };

/** Theme clair ou sombre.
 * @returns {[("light"|"dark"), () => void, boolean]} theme, bascule, et vrai
 */
export function useTheme() {
  const [choice, setChoice] = useState(() => storage.get(KEY, null));
  const [system, setSystem] = useState(systemTheme);

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return undefined;
    const onChange = (e) => setSystem(e.matches ? "dark" : "light");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const theme = choice ?? system;

  useLayoutEffect(() => {
    const racine = document.documentElement;
    // Changer de theme ne fait rien bouger : transitions coupees le temps
    // d'une image.
    racine.classList.add("no-transition");
    racine.dataset.theme = theme;
    const reprise = requestAnimationFrame(() => racine.classList.remove("no-transition"));

    // La barre d'adresse suit le theme affiche, pas seulement celui du systeme
    for (const balise of document.querySelectorAll('meta[name="theme-color"]')) {
      balise.removeAttribute("media");
      balise.setAttribute("content", COULEUR_BARRE[theme]);
    }
    return () => cancelAnimationFrame(reprise);
  }, [theme]);

  const toggle = useCallback(() => {
    const next = theme === "dark" ? "light" : "dark";
    storage.set(KEY, next);
    setChoice(next);
  }, [theme]);

  return [theme, toggle, choice === null];
}
