/** Diffusion de la fonction de traduction dans l'arbre React.
 *
 * Passer `t` en prop a chaque composant deviendrait vite illisible : un
 * contexte evite le "prop drilling" sur une valeur dont presque tous les
 * composants ont besoin.
 */
import { createContext, useContext } from "react";

// Valeur par defaut : identite. Un composant rendu hors du provider
// affichera la cle brute au lieu de planter.
const I18nContext = createContext((key) => key);

export function I18nProvider({ t, children }) {
  return <I18nContext.Provider value={t}>{children}</I18nContext.Provider>;
}

/** Recupere la fonction de traduction courante. */
// Le provider et son hook vont par paire et restent volontairement dans le
// meme fichier ; le rafraichissement a chaud recharge simplement le module.
// eslint-disable-next-line react-refresh/only-export-components
export function useT() {
  return useContext(I18nContext);
}
