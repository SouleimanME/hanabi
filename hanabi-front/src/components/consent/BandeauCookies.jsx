/** Bandeau de consentement, non bloquant. Refuser a le même bouton et la même
 *  place qu'accepter : la CNIL demande que refuser soit aussi simple. */
import { useLayoutEffect, useRef } from "react";
import { useT } from "../../i18n/context.jsx";

export function BandeauCookies({ onAccepter, onRefuser, onPersonnaliser, onEnSavoirPlus }) {
  const t = useT();
  const bandeau = useRef(null);

  // Sa hauteur remonte les notifications, qui s'afficheraient dessous
  useLayoutEffect(() => {
    const noeud = bandeau.current;
    const racine = document.documentElement;
    if (!noeud || typeof ResizeObserver === "undefined") return undefined;
    const observateur = new ResizeObserver(([entree]) => {
      const hauteur = entree.borderBoxSize?.[0]?.blockSize ?? noeud.offsetHeight;
      // Plus l'écart qui sépare deux surfaces posées l'une sur l'autre
      racine.style.setProperty("--hauteur-bandeau", `${Math.ceil(hauteur) + 8}px`);
    });
    observateur.observe(noeud);
    return () => {
      observateur.disconnect();
      racine.style.removeProperty("--hauteur-bandeau");
    };
  }, []);

  return (
    <section
      ref={bandeau}
      className="consent"
      aria-labelledby="consent-titre"
      aria-describedby="consent-texte"
    >
      <h2 id="consent-titre">{t("consentTitle")}</h2>
      <p id="consent-texte">{t("consentText")}</p>
      <div className="consent-actions">
        <button type="button" className="btn btn-quiet" onClick={onRefuser}>
          {t("consentRefuse")}
        </button>
        <button type="button" className="btn btn-quiet" onClick={onAccepter}>
          {t("consentAccept")}
        </button>
      </div>
      <p className="consent-liens">
        <button type="button" className="link" onClick={onPersonnaliser}>
          {t("consentCustomize")}
        </button>
        <button type="button" className="link" onClick={onEnSavoirPlus}>
          {t("consentMore")}
        </button>
      </p>
    </section>
  );
}
