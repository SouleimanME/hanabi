/** Point d'entree de l'application.
 *
 * La boutique est chargee en differe pour que Vite en fasse un lot separe,
 * avec sa propre feuille de styles.
 */
import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";

const Shop = lazy(() => import("./App.jsx"));

createRoot(document.getElementById("root")).render(
  <StrictMode>
    {/* Pas d'ecran de chargement : le lot est precharge par Vite, un
        indicateur qui clignote serait plus genant que l'attente. */}
    <Suspense fallback={null}>
      <Shop />
    </Suspense>
  </StrictMode>,
);
