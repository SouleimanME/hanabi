import { useState, useEffect, useMemo } from "react";
import { Orders } from "../lib/api.js";
import { SHIPPING_CENTS, FREE_SHIPPING_CENTS } from "../lib/constants.js";

/**
 * Montants du panier, calcules par le serveur.
 *
 * Regle de securite : le total qui fait foi vient toujours de l'API, jamais du
 * navigateur. L'estimation locale ci-dessous ne sert qu'a eviter un panier
 * vide a l'ecran pendant l'aller-retour reseau, et est remplacee des que la
 * reponse arrive.
 *
 * @param {{id: number, qty: number}[]} items lignes du panier (etat stable)
 * @param {string|null} promoCode code promo applique
 * @param {number} localSubtotalCents sous-total estime localement
 * @param {(message: string) => void} onPromoRejected appele si le serveur refuse le code
 */
export function usePricing(items, promoCode, localSubtotalCents, onPromoRejected) {
  const [quote, setQuote] = useState(null);

  useEffect(() => {
    if (items.length === 0) {
      setQuote(null);
      return;
    }

    // Le drapeau evite qu'une reponse tardive n'ecrase un devis plus recent.
    let cancelled = false;
    (async () => {
      const payload = items.map((line) => ({ product_id: line.id, qty: line.qty }));
      try {
        const result = await Orders.quote(payload, promoCode);
        if (!cancelled) setQuote(result);
      } catch (e) {
        if (cancelled) return;
        // Un code devenu invalide (expire, seuil non atteint) est signale et
        // retire, plutot que de bloquer le panier.
        if (promoCode) onPromoRejected(e.message);
        else setQuote(null);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [items, promoCode, onPromoRejected]);

  const estimate = useMemo(() => {
    const shipping =
      localSubtotalCents === 0 || localSubtotalCents >= FREE_SHIPPING_CENTS ? 0 : SHIPPING_CENTS;
    return {
      subtotal_cents: localSubtotalCents,
      discount_cents: 0,
      shipping_cents: shipping,
      total_cents: localSubtotalCents + shipping,
      promo: null,
    };
  }, [localSubtotalCents]);

  return quote ?? estimate;
}
