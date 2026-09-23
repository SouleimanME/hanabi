import { useState, useEffect, useCallback } from "react";
import { Products } from "../lib/api.js";

/** Charge le catalogue et le tient a jour selon les filtres actifs. */
export function useCatalog({ category, query, sort, lang }) {
  const [catalog, setCatalog] = useState({});
  const [products, setProducts] = useState([]);
  const [featured, setFeatured] = useState([]);
  const [error, setError] = useState(null);
  // Deux etats de chargement distincts, pour deux traitements visuels :, `loading`
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const remember = useCallback((items) => {
    setCatalog((current) => {
      const next = { ...current };
      for (const product of items) next[product.id] = product;
      return next;
    });
  }, []);

  const reload = useCallback(async () => {
    setRefreshing(true);
    try {
      const data = await Products.list({ category, q: query, sort, lang });
      setProducts(data);
      remember(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [category, query, sort, lang, remember]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    // Le drapeau evite qu'une reponse lente pour une langue abandonnee
    // ecrase le resultat d'une langue choisie entre-temps.
    let cancelled = false;
    (async () => {
      try {
        const items = await Products.featured(lang);
        if (!cancelled) setFeatured(items);
      } catch {
        if (!cancelled) setFeatured([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lang]);

  return { catalog, products, featured, error, loading, refreshing, reload, remember };
}
