import { useMemo, useCallback } from "react";
import { useLocalStorageState } from "./useLocalStorageState.js";

/** Resultats possibles d'un ajout au panier. */
export const ADD_RESULT = {
  ADDED: "added",
  MAX_STOCK: "max-stock",
  UNAVAILABLE: "unavailable",
  // Objet à déclinaisons ajouté sans en choisir une : la fiche doit s'ouvrir
  CHOOSE: "choose",
};

/** Clé d'une ligne : l'objet, et la déclinaison s'il en a. */
export const cleDeLigne = (id, v) => (v ? `${id}:${v}` : String(id));

const declinaison = (product, v) => (v ? product?.variantes?.find((x) => x.id === v) : null);

/** Panier persistant. Une ligne vaut `{ id, v, qty }`, `v` la déclinaison.
 * @param {Record<number, object>} catalog index id -> produit
 */
export function useCart(catalog) {
  const [items, setItems] = useLocalStorageState("cart", []);

  // Une ligne dont le produit ou la déclinaison est inconnu est ignoree plutot
  // que d'afficher un trou : produit supprime, couleur retiree, pas encore charge.
  const lines = useMemo(
    () =>
      items
        .map((line) => {
          const product = catalog[line.id];
          const variante = declinaison(product, line.v);
          const aDesDeclinaisons = Boolean(product?.variantes?.length);
          if (!product || (aDesDeclinaisons && !variante) || (!aDesDeclinaisons && line.v)) {
            return null;
          }
          return {
            ...line,
            cle: cleDeLigne(line.id, line.v),
            product,
            variante,
            prix: variante ? variante.price_cents : product.price_cents,
            stock: variante ? variante.stock : product.stock,
            art: variante?.image || product.art,
          };
        })
        .filter(Boolean),
    [items, catalog],
  );

  const count = useMemo(() => lines.reduce((sum, l) => sum + l.qty, 0), [lines]);

  const subtotalCents = useMemo(() => lines.reduce((sum, l) => sum + l.prix * l.qty, 0), [lines]);

  /** Ajoute `qty` unites, en plafonnant au stock disponible.
   * @returns {string} une valeur de ADD_RESULT
   */
  const add = useCallback(
    (id, qty = 1, v = null) => {
      const product = catalog[id];
      if (!product) return ADD_RESULT.UNAVAILABLE;
      if (product.variantes?.length && !v) return ADD_RESULT.CHOOSE;
      const variante = declinaison(product, v);
      const stock = variante ? variante.stock : product.stock;
      if (stock === 0 || (v && !variante)) return ADD_RESULT.UNAVAILABLE;

      const cle = cleDeLigne(id, v);
      const existing = items.find((l) => cleDeLigne(l.id, l.v) === cle);
      const current = existing ? existing.qty : 0;
      const next = Math.min(current + qty, stock);
      if (next === current) return ADD_RESULT.MAX_STOCK;

      setItems(
        existing
          ? items.map((l) => (cleDeLigne(l.id, l.v) === cle ? { ...l, qty: next } : l))
          : [...items, v ? { id, v, qty: next } : { id, qty: next }],
      );
      return ADD_RESULT.ADDED;
    },
    [catalog, items, setItems],
  );

  const setQty = useCallback(
    (cleBrute, qty) => {
      const cle = String(cleBrute);
      const ligne = lines.find((l) => l.cle === cle);
      const stock = ligne?.stock ?? qty;
      setItems((current) =>
        current.map((l) =>
          cleDeLigne(l.id, l.v) === cle ? { ...l, qty: Math.max(1, Math.min(qty, stock)) } : l,
        ),
      );
    },
    [lines, setItems],
  );

  const remove = useCallback(
    (cle) => setItems((current) => current.filter((l) => cleDeLigne(l.id, l.v) !== String(cle))),
    [setItems],
  );

  const clear = useCallback(() => setItems([]), [setItems]);

  /** Format attendu par l'API pour un devis ou une commande. */
  const toPayload = useCallback(
    () =>
      items.map((l) =>
        l.v ? { product_id: l.id, variante_id: l.v, qty: l.qty } : { product_id: l.id, qty: l.qty },
      ),
    [items],
  );

  return { items, lines, count, subtotalCents, add, setQty, remove, clear, toPayload };
}
