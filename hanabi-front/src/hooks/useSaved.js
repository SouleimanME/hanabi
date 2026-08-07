import { useCallback } from "react";
import { useLocalStorageState } from "./useLocalStorageState.js";

/**
 * Articles mis de cote depuis le panier (« Garder pour plus tard »).
 *
 * A distinguer des favoris : le favori est un souhait, l'article enregistre
 * est une intention d'achat qu'on differe. Devant la caisse, on ne renonce pas
 * a un article, on le repose sur le comptoir - et il ne doit ni gonfler le
 * total, ni disparaitre au rechargement de la page.
 *
 * Comme le panier, seul l'identifiant est conserve : prix, stock et nom sont
 * relus dans le catalogue a l'affichage, jamais figes dans le localStorage.
 */
export function useSaved() {
  const [ids, setIds] = useLocalStorageState("saved", []);

  const has = useCallback((id) => ids.includes(id), [ids]);

  const save = useCallback(
    (id) => setIds((current) => (current.includes(id) ? current : [id, ...current])),
    [setIds],
  );

  const remove = useCallback(
    (id) => setIds((current) => current.filter((x) => x !== id)),
    [setIds],
  );

  return { ids, count: ids.length, has, save, remove };
}
