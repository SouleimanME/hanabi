/** Point d'entree de l'application.
 *
 * Deux interfaces distinctes cohabitent : la boutique et le back-office. Elles
 * ont chacune leur feuille de styles, avec des regles globales concurrentes
 * (reset, styles de `button`). Les charger toutes les deux ferait dependre le
 * rendu de l'ordre d'arrivee des fichiers.
 *
 * Les deux sont donc chargees en differe : Vite en fait des lots separes, et
 * chaque route ne recupere que son propre CSS. Cela evite au passage
 * d'envoyer le back-office a tous les visiteurs de la boutique.
 */
import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";

const Shop = lazy(() => import("./App.jsx"));
const Admin = lazy(() => import("./admin/Admin.jsx"));

const isAdminRoute = window.location.pathname.startsWith("/admin");
const Screen = isAdminRoute ? Admin : Shop;

createRoot(document.getElementById("root")).render(
  <StrictMode>
    {/* Pas d'ecran de chargement : le lot est precharge par Vite, un
        indicateur qui clignote serait plus genant que l'attente. */}
    <Suspense fallback={null}>
      <Screen />
    </Suspense>
  </StrictMode>,
);
