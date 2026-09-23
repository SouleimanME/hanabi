/** Point d'entree : la boutique ou le back-office selon le chemin. */
import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";

const Shop = lazy(() => import("./App.jsx"));
const Admin = lazy(() => import("./admin/Admin.jsx"));

const Screen = window.location.pathname.startsWith("/admin") ? Admin : Shop;

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Suspense fallback={null}>
      <Screen />
    </Suspense>
  </StrictMode>,
);
