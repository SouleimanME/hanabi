import { useState, useEffect } from "react";

/** Renvoie `value` en differe : la valeur ne se propage qu'apres `delay` millisecondes sans nouveau changement. */
export function useDebouncedValue(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
