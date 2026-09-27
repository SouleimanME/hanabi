/** Photos d'une fiche en plein écran, ouvertes d'une tape sur téléphone :
 *  pincer ou toucher pour zoomer, glisser pour passer à la suivante. */
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";
import { useEscapeKey } from "../../hooks/useEscapeKey.js";
import { ProductArt } from "../brand/ProductArt.jsx";
import { ZoomPhoto } from "./ZoomPhoto.jsx";

export default function Visionneuse({ photos, depart = 0, nom, onFermer }) {
  const t = useT();
  const piege = useFocusTrap();
  const [i, setI] = useState(depart);
  const aller = (pas) => setI((n) => (n + pas + photos.length) % photos.length);
  useEscapeKey(onFermer);

  // La page ne défile plus sous la visionneuse
  useEffect(() => {
    const racine = document.documentElement;
    const avant = racine.style.overflow;
    racine.style.overflow = "hidden";
    return () => {
      racine.style.overflow = avant;
    };
  }, []);

  const clavier = (e) => {
    // Photo agrandie, les flèches la déplacent : ZoomPhoto a déjà pris la touche
    if (e.defaultPrevented) return;
    const pas = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!pas || photos.length < 2) return;
    e.preventDefault();
    aller(pas);
  };

  return (
    <div
      ref={piege}
      className="visionneuse"
      role="dialog"
      aria-modal="true"
      aria-label={nom}
      onKeyDown={clavier}
    >
      <div className="visionneuse-barre">
        <p className="visionneuse-compte" aria-live="polite">
          {i + 1} / {photos.length}
        </p>
        <button
          type="button"
          className="visionneuse-fermer"
          onClick={onFermer}
          aria-label={t("close")}
        >
          <X size={24} aria-hidden="true" />
        </button>
      </div>
      <div className="visionneuse-cadre">
        <ZoomPhoto
          key={i}
          plein
          libelle={t("viewOf", { name: nom, n: i + 1, total: photos.length })}
          aide="visionneuse-aide"
          onBalayage={photos.length > 1 ? aller : undefined}
        >
          <ProductArt art={photos[i]} alt="" scene taille="100vw" priorite />
        </ZoomPhoto>
      </div>
      <p className="visionneuse-aide" id="visionneuse-aide">
        {photos.length > 1 ? t("zoomHintFull") : t("zoomHintFullOne")}
      </p>
    </div>
  );
}
