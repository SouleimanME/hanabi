import { useMemo, useCallback } from "react";
import { useLocalStorageState } from "./useLocalStorageState.js";

/** Resultats possibles d'un ajout au panier. */
export const ADD_RESULT = {
  ADDED: "added",
  MAX_STOCK: "max-stock",
  UNAVAILABLE: "unavailable",
};

/**
 * Panier persistant.
 *
 * Seuls l'identifiant et la quantite sont stockes : prix, nom et stock sont
 * relus depuis le catalogue a chaque rendu. Un prix modifie en base est donc
 * immediatement repercute, au lieu de rester fige dans le localStorage.
 *
 * @param {Record<number, object>} catalog index id -> produit
 */
export function useCart(catalog) {
  const [items, setItems] = useLocalStorageState("cart", []);

  // Une ligne dont le produit est inconnu est ignoree plutot que d'afficher
  // un trou : cela couvre le produit supprime ou pas encore charge.
  const lines = useMemo(
    () =>
      items.map((line) => ({ ...line, product: catalog[line.id] })).filter((line) => line.product),
    [items, catalog],
  );

  const count = useMemo(() => lines.reduce((sum, l) => sum + l.qty, 0), [lines]);

  const subtotalCents = useMemo(
    () => lines.reduce((sum, l) => sum + l.product.price_cents * l.qty, 0),
    [lines],
  );

  /**
   * Ajoute `qty` unites, en plafonnant au stock disponible.
   * @returns {string} une valeur de ADD_RESULT
   */
  const add = useCallback(
    (id, qty = 1) => {
      const product = catalog[id];
      if (!product || product.stock === 0) return ADD_RESULT.UNAVAILABLE;

      const existing = items.find((l) => l.id === id);
      const current = existing ? existing.qty : 0;
      const next = Math.min(current + qty, product.stock);
      if (next === current) return ADD_RESULT.MAX_STOCK;

      setItems(
        existing
          ? items.map((l) => (l.id === id ? { ...l, qty: next } : l))
          : [...items, { id, qty: next }],
      );
      return ADD_RESULT.ADDED;
    },
    [catalog, items, setItems],
  );

  const setQty = useCallback(
    (id, qty) => {
      const stock = catalog[id]?.stock ?? qty;
      setItems((current) =>
        current.map((l) => (l.id === id ? { ...l, qty: Math.max(1, Math.min(qty, stock)) } : l)),
      );
    },
    [catalog, setItems],
  );

  const remove = useCallback(
    (id) => setItems((current) => current.filter((l) => l.id !== id)),
    [setItems],
  );

  const clear = useCallback(() => setItems([]), [setItems]);

  /** Format attendu par l'API pour un devis ou une commande. */
  const toPayload = useCallback(
    () => items.map((l) => ({ product_id: l.id, qty: l.qty })),
    [items],
  );

  return { items, lines, count, subtotalCents, add, setQty, remove, clear, toPayload };
}
