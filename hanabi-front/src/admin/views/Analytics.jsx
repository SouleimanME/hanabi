/** Analytique : six vues calculees a la demande sur la base transactionnelle.
 *  Une vue deja chargee reste en memoire le temps de l'onglet. */
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { Chargement } from "../ui.jsx";
import { Overview } from "./analytics/Overview.jsx";
import { Profitability } from "./analytics/Profitability.jsx";
import { Forecast } from "./analytics/Forecast.jsx";
import { Cohorts } from "./analytics/Cohorts.jsx";
import { Segments } from "./analytics/Segments.jsx";
import { Affinities } from "./analytics/Affinities.jsx";

const VUES = [
  { key: "overview", label: "Vue d'ensemble" },
  { key: "profit", label: "Rentabilité" },
  { key: "forecast", label: "Tendance" },
  { key: "cohorts", label: "Cohortes" },
  { key: "segments", label: "Segments" },
  { key: "affinities", label: "Affinités" },
];

const PERIODES = [
  { days: 30, label: "30 jours" },
  { days: 90, label: "90 jours" },
  { days: 365, label: "12 mois" },
];

export function Analytics({ flash }) {
  const [view, setView] = useState("overview");
  const [days, setDays] = useState(30);
  const [data, setData] = useState({});
  const [busy, setBusy] = useState(false);

  // La rentabilite relit le meme appel que la vue d'ensemble
  const routes = {
    overview: `/admin/analytics?months=12&days=${days}`,
    profit: `/admin/analytics?months=12&days=${days}`,
    forecast: "/admin/analytics/forecast?months=12&horizon=3",
    cohorts: "/admin/analytics/cohorts?months=12",
    segments: "/admin/analytics/segments",
    affinities: "/admin/analytics/affinities?limit=12",
  };
  const cle = ["overview", "profit"].includes(view) ? `overview:${days}` : view;

  useEffect(() => {
    let annule = false;
    if (data[cle]) return undefined;
    setBusy(true);
    api(routes[view])
      .then((res) => !annule && setData((d) => ({ ...d, [cle]: res })))
      .catch((e) => flash(e.message, "err"))
      .finally(() => !annule && setBusy(false));
    // Sans annulation, la reponse tardive d'une vue quittee s'ecrirait
    return () => {
      annule = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cle]);

  const courant = data[cle];

  return (
    <div>
      <div className="adm-subnav">
        <div className="adm-segments" role="group" aria-label="Vues analytiques">
          {VUES.map((v) => (
            <button
              key={v.key}
              className="adm-subnav-btn"
              aria-pressed={view === v.key}
              onClick={() => setView(v.key)}
            >
              {v.label}
            </button>
          ))}
        </div>
        {view === "overview" && (
          <div className="adm-segments" role="group" aria-label="Période">
            {PERIODES.map((p) => (
              <button
                key={p.days}
                className="adm-subnav-btn"
                aria-pressed={days === p.days}
                onClick={() => setDays(p.days)}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
        {busy && <span className="adm-spin" role="status" aria-label="Calcul en cours" />}
      </div>

      {!courant && <Chargement>Calcul des indicateurs</Chargement>}
      {courant && view === "overview" && <Overview data={courant} days={days} />}
      {courant && view === "profit" && <Profitability data={courant} />}
      {courant && view === "forecast" && <Forecast data={courant} />}
      {courant && view === "cohorts" && <Cohorts data={courant} />}
      {courant && view === "segments" && <Segments data={courant} />}
      {courant && view === "affinities" && <Affinities data={courant} />}
    </div>
  );
}
