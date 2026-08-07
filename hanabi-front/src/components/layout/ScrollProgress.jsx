/** Fil de progression du defilement, colle sous l'en-tete.
 *
 * Repere d'avancement dans la page. L'ecriture se fait directement dans une
 * variable CSS via la ref, sans passer par l'etat React : le defilement emet
 * des dizaines d'evenements par seconde, un re-rendu a chaque fois saccaderait.
 *
 * La mesure est repoussee dans un requestAnimationFrame afin de ne jamais
 * lire la geometrie du document pendant le traitement de l'evenement, ce qui
 * forcerait un recalcul de mise en page synchrone a chaque pixel parcouru.
 */
import { useEffect, useRef } from "react";

export function ScrollProgress() {
  const barRef = useRef(null);

  useEffect(() => {
    let queued = false;

    const measure = () => {
      queued = false;
      const doc = document.documentElement;
      const scrollable = doc.scrollHeight - window.innerHeight;
      const ratio = scrollable > 0 ? window.scrollY / scrollable : 0;
      barRef.current?.style.setProperty("--p", Math.min(1, Math.max(0, ratio)));
    };

    const onScroll = () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(measure);
    };

    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return <div className="scrollbar-progress" ref={barRef} aria-hidden="true" />;
}
