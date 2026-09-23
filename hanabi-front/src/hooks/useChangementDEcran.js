import { useEffect, useRef } from "react";

const MARQUE = "Hanabi 花火";

/** Titre de l'onglet et focus, à chaque changement d'écran.
 *
 * Sans eux, l'onglet s'appelait toujours pareil (historique, favoris, partage)
 * et un lecteur d'écran restait sur le bouton cliqué, dans une page qui n'était
 * plus là. Le focus part sur le contenu principal, pas au premier chargement.
 * @param {string} cle identifiant de l'écran affiché (vue, et fiche ouverte)
 * @param {string|null} titre titre de la page, sans la marque ; null à l'accueil
 * @param {string} accroche sous-titre de la marque, pour l'accueil
 */
export function useChangementDEcran(cle, titre, accroche) {
  useEffect(() => {
    document.title = titre ? `${titre} · ${MARQUE}` : `${MARQUE} · ${accroche}`;
  }, [titre, accroche]);

  const premier = useRef(true);
  useEffect(() => {
    if (premier.current) {
      premier.current = false;
      return;
    }
    const contenu = document.getElementById("contenu");
    if (!contenu) return;
    if (!contenu.hasAttribute("tabindex")) contenu.setAttribute("tabindex", "-1");
    contenu.focus({ preventScroll: true });
  }, [cle]);
}
