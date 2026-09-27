import { useState, useEffect, useCallback, useRef } from "react";
import { Products } from "../lib/api.js";

/* Dernier catalogue reçu, gardé dans le navigateur : au retour sur le site, la
   grille s'affiche tout de suite, puis la réponse du serveur la remplace. Le
   serveur gratuit s'endort ; sans cela, un visiteur fidèle attendait son réveil. */
const CLE = "hanabi:catalogue:v1";
// Quelques vues suffisent : langue, famille et tri de la page d'accueil
const VUES_MAX = 8;

function lireCache(vue) {
  try {
    return JSON.parse(localStorage.getItem(CLE) || "{}")[vue]?.donnees ?? null;
  } catch {
    return null;
  }
}

function ecrireCache(vue, donnees) {
  // Une photo encore embarquée pèserait des mégaoctets : on n'en garde pas
  if (JSON.stringify(donnees).includes('"data:')) return;
  try {
    const cache = JSON.parse(localStorage.getItem(CLE) || "{}");
    cache[vue] = { le: Date.now(), donnees };
    const gardees = Object.entries(cache)
      .sort(([, a], [, b]) => b.le - a.le)
      .slice(0, VUES_MAX);
    localStorage.setItem(CLE, JSON.stringify(Object.fromEntries(gardees)));
  } catch {
    /* navigation privée ou quota : le catalogue se charge comme avant */
  }
}

/** Charge le catalogue et le tient a jour selon les filtres actifs. */
export function useCatalog({ category, query, sort, lang }) {
  // Une recherche n'est pas mise en cache : elle change à chaque frappe
  const vue = query ? null : `${lang}|${category}|${sort}`;
  const vueFeatured = `featured|${lang}`;
  const initial = useRef(vue ? lireCache(vue) : null);

  const [catalog, setCatalog] = useState(() =>
    Object.fromEntries((initial.current || []).map((p) => [p.id, p])),
  );
  const [products, setProducts] = useState(() => initial.current || []);
  const [featured, setFeatured] = useState(() => lireCache(vueFeatured) || []);
  const [error, setError] = useState(null);
  // Deux etats de chargement distincts, pour deux traitements visuels :, `loading`
  const [loading, setLoading] = useState(() => !initial.current);
  const [refreshing, setRefreshing] = useState(false);

  const remember = useCallback((items) => {
    setCatalog((current) => {
      const next = { ...current };
      for (const product of items) next[product.id] = product;
      return next;
    });
  }, []);

  const reload = useCallback(async () => {
    const enCache = vue ? lireCache(vue) : null;
    if (enCache) {
      setProducts(enCache);
      setLoading(false);
    }
    // La grille en cache reste pleine : la mise à jour se fait sans la griser
    setRefreshing(!enCache);
    try {
      const data = await Products.list({ category, q: query, sort, lang });
      setProducts(data);
      remember(data);
      setError(null);
      if (vue) ecrireCache(vue, data);
    } catch (e) {
      // Une grille déjà affichée vaut mieux qu'un message d'erreur
      if (!enCache) setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [category, query, sort, lang, remember, vue]);

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
        if (!cancelled) {
          setFeatured(items);
          ecrireCache(vueFeatured, items);
        }
      } catch {
        if (!cancelled) setFeatured((actuels) => actuels);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lang, vueFeatured]);

  return { catalog, products, featured, error, loading, refreshing, reload, remember };
}
