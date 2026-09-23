/** Tableau de bord : chiffres cles, profil clients explorable, dernieres commandes. */
import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { api } from "../api.js";
import { eur, fmtDate, num, pct } from "../format.js";
import { BarChart } from "../charts.jsx";
import { Chargement, SousTitre, StatusBadge } from "../ui.jsx";

/* Le graphique affiche des libelles, l'API attend les codes stockes en base */
const CIVILITE_LIBELLES = {
  M: "Homme (M.)",
  F: "Femme (Mme)",
  N: "Non binaire",
  "?": "Non renseigné",
};
const CIVILITE_CLES = Object.fromEntries(
  Object.entries(CIVILITE_LIBELLES).map(([cle, libelle]) => [libelle, cle]),
);

/** Portrait d'achat du segment choisi. Sans filtre, celui de toute la
 *  clientele : c'est lui qui donne l'echelle. */
function SegmentDetail({ filtre, portrait, onReset }) {
  const criteres = Object.entries(filtre);
  const titre = criteres.length
    ? criteres.map(([dim, val]) => (dim === "civility" ? CIVILITE_LIBELLES[val] : val)).join(" · ")
    : "Toute la clientèle";

  if (!portrait) {
    return (
      <div className="segment-panneau">
        <Chargement>Calcul du segment</Chargement>
      </div>
    );
  }

  const chiffres = [
    { valeur: num(portrait.customers), libelle: "clients" },
    { valeur: pct(portrait.buyer_rate), libelle: "ont acheté" },
    { valeur: eur(portrait.revenue_cents), libelle: "chiffre d'affaires" },
    { valeur: eur(portrait.aov_cents), libelle: "panier moyen" },
    { valeur: eur(portrait.value_per_customer_cents), libelle: "valeur par client" },
  ];

  return (
    <section className={"segment-panneau" + (criteres.length ? " filtre" : "")} aria-live="polite">
      <div className="segment-entete">
        <div>
          <span className="ch-title">Portrait d&apos;achat</span>
          <strong className="segment-titre">{titre}</strong>
        </div>
        {criteres.length > 0 && (
          <button className="adm-btn sm" onClick={onReset}>
            <X size={14} aria-hidden="true" /> Tout afficher
          </button>
        )}
      </div>

      {portrait.customers === 0 ? (
        <p className="adm-legend">Aucun client ne correspond à cette combinaison.</p>
      ) : (
        <>
          <dl className="segment-chiffres">
            {chiffres.map((c) => (
              <div key={c.libelle}>
                <dt className="segment-lbl">{c.libelle}</dt>
                <dd className="segment-val num">{c.valeur}</dd>
              </div>
            ))}
          </dl>

          <div className="segment-grille">
            <div className="segment-bloc">
              <span className="ch-title">Ce qu&apos;ils achètent</span>
              <ol className="segment-liste">
                {portrait.top_products.map((p) => (
                  <li key={p.name}>
                    <span className="segment-nom">{p.name}</span>
                    <span className="num">{num(p.units)} u.</span>
                    <span className="num segment-second">{eur(p.revenue_cents)}</span>
                  </li>
                ))}
              </ol>
            </div>

            {portrait.best_customer && (
              <div className="segment-bloc">
                <span className="ch-title">Meilleur client</span>
                <strong className="segment-nom-fort">{portrait.best_customer.name}</strong>
                <span className="segment-second">{portrait.best_customer.email}</span>
                <span className="segment-second">
                  {portrait.best_customer.city || "ville non renseignée"} ·{" "}
                  {portrait.best_customer.orders} commandes
                </span>
                <span className="segment-val num">{eur(portrait.best_customer.total_cents)}</span>
              </div>
            )}

            {portrait.biggest_order && (
              <div className="segment-bloc">
                <span className="ch-title">Plus grosse commande</span>
                <strong className="segment-nom-fort code">{portrait.biggest_order.number}</strong>
                <span className="segment-second">{portrait.biggest_order.email}</span>
                <span className="segment-second">
                  {portrait.biggest_order.created_at
                    ? fmtDate(portrait.biggest_order.created_at)
                    : ""}
                </span>
                <span className="segment-val num">{eur(portrait.biggest_order.total_cents)}</span>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}

export function Dashboard({ stats }) {
  const d = stats.demographics || {};
  const civ = d.civility || {};
  const ages = d.age_buckets || {};

  const civData = [
    { key: CIVILITE_LIBELLES.M, value: civ.M || 0 },
    { key: CIVILITE_LIBELLES.F, value: civ.F || 0 },
    { key: CIVILITE_LIBELLES.N, value: civ.N || 0 },
    { key: CIVILITE_LIBELLES["?"], value: civ["?"] || 0 },
  ].filter((x) => x.value > 0);
  const ageData = Object.entries(ages)
    .filter(([k, v]) => k !== "?" && v > 0)
    .map(([k, v]) => ({ key: k, value: v }));
  const cityData = (d.top_cities || []).map((c) => ({ key: c.city, value: c.count }));

  // Les trois criteres se cumulent ; un second clic sur le meme le retire
  const [filtre, setFiltre] = useState({});
  const [portrait, setPortrait] = useState(null);

  const choisir = (dimension, valeur) =>
    setFiltre((f) => {
      const suivant = { ...f };
      if (valeur == null) delete suivant[dimension];
      else suivant[dimension] = valeur;
      return suivant;
    });

  useEffect(() => {
    const query = new URLSearchParams(filtre).toString();
    let annule = false;
    api(`/admin/analytics/audience${query ? `?${query}` : ""}`)
      .then((r) => !annule && setPortrait(r))
      .catch(() => !annule && setPortrait(null));
    return () => {
      annule = true;
    };
  }, [filtre]);

  const kpis = [
    { label: "Chiffre d'affaires", value: eur(stats.revenue_cents) },
    { label: "Commandes", value: num(stats.order_count) },
    { label: "Clients", value: num(stats.user_count) },
    { label: "Produits actifs", value: num(stats.product_count) },
  ];

  return (
    <div>
      <dl className="adm-cards">
        {kpis.map((c) => (
          <div key={c.label} className="adm-card">
            <dt className="adm-card-lbl">{c.label}</dt>
            <dd className="adm-card-val num">{c.value}</dd>
          </div>
        ))}
      </dl>

      {stats.low_stock_count > 0 && (
        <p className="adm-warn">
          {stats.low_stock_count} produit{stats.low_stock_count > 1 ? "s" : ""} avec un stock faible
          (4 ou moins)
        </p>
      )}
      {stats.pending_alerts > 0 && (
        <p className="adm-warn">
          {stats.pending_alerts} alerte{stats.pending_alerts > 1 ? "s" : ""} de retour en stock en
          attente
        </p>
      )}

      <SousTitre note="Choisis une tranche, une ville ou un genre pour voir ce que ce segment achète. Les critères se combinent ; un second clic retire le filtre.">
        Profil clients
      </SousTitre>
      <div className="viz-grid">
        {civData.length > 0 ? (
          <BarChart
            data={civData}
            title="Genre"
            format={num}
            selected={filtre.civility && CIVILITE_LIBELLES[filtre.civility]}
            onSelect={(cle) => choisir("civility", cle && CIVILITE_CLES[cle])}
          />
        ) : (
          <div className="viz-block viz-empty">Pas encore de données de genre</div>
        )}
        {ageData.length > 0 ? (
          <BarChart
            data={ageData}
            title="Tranches d'âge"
            format={num}
            selected={filtre.age}
            onSelect={(cle) => choisir("age", cle)}
          />
        ) : (
          <div className="viz-block viz-empty">Pas encore de données d&apos;âge</div>
        )}
        {cityData.length > 0 ? (
          <BarChart
            data={cityData}
            title="Villes"
            format={num}
            selected={filtre.city}
            onSelect={(cle) => choisir("city", cle)}
          />
        ) : (
          <div className="viz-block viz-empty">Pas encore de données de ville</div>
        )}
      </div>

      <SegmentDetail filtre={filtre} portrait={portrait} onReset={() => setFiltre({})} />

      <SousTitre>Dernières commandes</SousTitre>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Numéro</th>
              <th scope="col">Client</th>
              <th scope="col" className="num">
                Montant
              </th>
              <th scope="col">Statut</th>
              <th scope="col">Date</th>
            </tr>
          </thead>
          <tbody>
            {stats.recent_orders.map((o) => (
              <tr key={o.number}>
                <td className="code">{o.number}</td>
                <td>{o.email}</td>
                <td className="num">{eur(o.total_cents)}</td>
                <td>
                  <StatusBadge status={o.status} />
                </td>
                <td>{fmtDate(o.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
