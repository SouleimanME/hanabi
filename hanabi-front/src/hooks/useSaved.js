import { useCallback } from "react";
import { useLocalStorageState } from "./useLocalStorageState.js";

/** Articles mis de cote depuis le panier (« Garder pour plus tard »). */
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
