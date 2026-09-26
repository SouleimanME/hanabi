/** Conseil cadeau : la personne décrit à qui elle offre, le conseiller choisit
 *  dans la boutique et dit pourquoi. Absent si le serveur n'a pas de fournisseur. */
import { lazy, Suspense, useEffect, useState } from "react";
import { Conseil } from "../../lib/api.js";

// Téléchargé seulement si le conseiller répond, et plus bas que la sélection
const Conseiller = lazy(() => import("./Conseiller.jsx"));

export function ConseilCadeau(props) {
  const [actif, setActif] = useState(false);

  useEffect(() => {
    let vivant = true;
    Conseil.etat()
      .then((etat) => vivant && setActif(Boolean(etat?.actif)))
      .catch(() => {
        /* serveur injoignable : la section reste absente */
      });
    return () => {
      vivant = false;
    };
  }, []);

  // Le formulaire ne monte, et ne prépare sa preuve anti-robots, que si le conseiller répond
  return actif ? (
    <Suspense fallback={null}>
      <Conseiller {...props} />
    </Suspense>
  ) : null;
}
