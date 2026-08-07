import { useState, useEffect } from "react";
import { storage } from "../lib/storage.js";

/**
 * `useState` dont la valeur survit au rechargement de la page.
 *
 * La lecture initiale est paresseuse : elle ne touche au localStorage qu'au
 * premier rendu, pas a chaque re-rendu.
 *
 * @param {string} key cle de stockage (prefixee par la couche `storage`)
 * @param {*} initialValue valeur utilisee si rien n'est stocke
 */
export function useLocalStorageState(key, initialValue) {
  const [value, setValue] = useState(() => storage.get(key, initialValue));

  useEffect(() => {
    storage.set(key, value);
  }, [key, value]);

  return [value, setValue];
}
