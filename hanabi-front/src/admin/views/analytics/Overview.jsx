/** Vue d'ensemble : la periode comparee a la precedente, le cumul, le detail
 *  par reference. */
import { useState } from "react";

import { decimale, eur, fmtDate, num, pct, STATUS_LABELS } from "../../format.js";
import { axisEuro } from "../../chart-utils.js";
import { BarChart, LineChart } from "../../charts.jsx";
import { SERIES } from "../../palette.js";
import { Delta, SousTitre } from "../../ui.jsx";

const COLONNES = [
  { key: "name", label: "Produit", get: (p) => p.name },
  { key: "views", label: "Vues", get: (p) => p.views, num: true },
  { key: "orders", label: "Commandes", get: (p) => p.orders, num: true },
  { key: "units", label: "Unités", get: (p) => p.units, num: true },
  { key: "conversion", label: "Conversion", get: (p) => p.conversion, num: true },
  { key: "revenue", label: "CA", get: (p) => p.revenue_cents, num: true },
  { key: "price", label: "Prix", get: (p) => p.price_cents, num: true },
  { key: "rating", label: "Note", get: (p) => p.rating_avg, num: true },
  { key: "stock", label: "Stock", get: (p) => p.stock, num: true },
];

/** Conversion reperee par rapport aux usages : sous 5 % on s'inquiete, au-dessus
 *  de 10 % on met en avant. Le chiffre reste ecrit. */
function Conversion({ value }) {
  const ton = value >= 0.1 ? "ok" : value >= 0.05 ? "mid" : "low";
  return <span className={`conv conv-${ton}`}>{pct(value)}</span>;
}

export function Overview({ data, days }) {
  const [tri, setTri] = useState({ col: "revenue", asc: false });

  const k = data.kpis;
  const p = data.period;
  const c = p.current;

  const colonne = COLONNES.find((x) => x.key === tri.col) || COLONNES[5];
  const produits = [...data.products].sort((a, b) => {
    const va = colonne.get(a);
    const vb = colonne.get(b);
    const cmp = typeof va === "string" ? va.localeCompare(vb, "fr") : va - vb;
    return tri.asc ? cmp : -cmp;
  });
  const trier = (key) =>
    setTri((s) => (s.col === key ? { col: key, asc: !s.asc } : { col: key, asc: false }));

  const periode = [
    { label: "Chiffre d'affaires", value: eur(c.revenue_cents), delta: p.change.revenue_cents },
    { label: "Commandes", value: num(c.orders), delta: p.change.orders },
    { label: "Panier moyen", value: eur(c.aov_cents), delta: p.change.aov_cents },
    { label: "Fiches consultées", value: num(c.views), delta: p.change.views },
    { label: "Conversion", value: pct(c.conversion), delta: p.change.conversion },
    { label: "Nouveaux comptes", value: num(c.signups), delta: p.change.signups },
    { label: "Acheteurs", value: num(c.buyers), delta: p.change.buyers },
    {
      label: "Revenu par fiche vue",
      value: eur(c.revenue_per_view_cents),
      delta: p.change.revenue_per_view_cents,
    },
  ];

  const cumul = [
    { label: "CA depuis l'origine", value: eur(k.revenue_cents) },
    { label: "Clients", value: num(k.customers) },
    {
      label: "Clients acheteurs",
      value: pct(k.buyer_rate),
      hint: `${num(k.buyers)} sur ${num(k.customers)} inscrits`,
    },
    { label: "Taux de réachat", value: pct(k.repeat_rate), hint: "Revenus au moins une fois" },
    {
      label: "Revenu par acheteur",
      value: eur(k.revenue_per_buyer_cents),
      hint: "Plancher de la valeur vie client",
    },
  ];

  const serie = data.series;
  const mois = serie.map((m) => m.month.slice(2));
  const vus = [...data.products].sort((a, b) => b.views - a.views);
  const vendus = [...data.products].sort((a, b) => b.units - a.units);
  const ligne = (titre, valeurs, format, formatTick, hint) => (
    <LineChart
      title={titre}
      hint={hint}
      labels={mois}
      format={format}
      formatTick={formatTick}
      series={[{ key: titre, label: titre, color: SERIES[0], values: valeurs }]}
    />
  );

  return (
    <div>
      <SousTitre
        note={`Comparé aux ${days} jours précédents. « nouveau » signale une période précédente vide.`}
      >
        Sur {days} jours
      </SousTitre>
      <dl className="adm-cards adm-cards-4">
        {periode.map((carte) => (
          <div key={carte.label} className="adm-card">
            <dt className="adm-card-lbl">{carte.label}</dt>
            <dd className="adm-card-top">
              <span className="adm-card-val sm num">{carte.value}</span>
              <Delta value={carte.delta} />
            </dd>
          </div>
        ))}
      </dl>

      <SousTitre>Depuis l&apos;origine</SousTitre>
      <dl className="adm-cards adm-cards-5">
        {cumul.map((carte) => (
          <div key={carte.label} className="adm-card">
            <dt className="adm-card-lbl">{carte.label}</dt>
            <dd className="adm-card-val num">{carte.value}</dd>
            {carte.hint && <dd className="adm-card-hint">{carte.hint}</dd>}
          </div>
        ))}
      </dl>

      <SousTitre note="Une mesure par graphique : deux échelles sur un même repère fabriquent une corrélation que les données ne contiennent pas.">
        Évolution sur 12 mois
      </SousTitre>
      <div className="viz-grid viz-grid-2">
        {ligne(
          "Chiffre d'affaires",
          serie.map((m) => m.revenue_cents),
          eur,
          axisEuro,
        )}
        {ligne(
          "Commandes",
          serie.map((m) => m.orders),
          num,
        )}
        {ligne(
          "Audience",
          serie.map((m) => m.views),
          num,
          undefined,
          "fiches produit ouvertes",
        )}
        {ligne(
          "Nouveaux comptes",
          serie.map((m) => m.signups),
          num,
        )}
      </div>

      <SousTitre>Palmarès du catalogue</SousTitre>
      <div className="viz-grid viz-grid-2">
        <BarChart
          title="Audience par référence"
          hint="fiches ouvertes"
          data={vus.map((x) => ({ key: x.name, value: x.views }))}
          format={num}
        />
        <BarChart
          title="Ventes par référence"
          hint="unités écoulées"
          data={vendus.map((x) => ({ key: x.name, value: x.units }))}
          format={num}
        />
      </div>

      <SousTitre note="Un article très vu et peu commandé signale un prix ou une fiche à revoir ; l'inverse, une référence à mettre en avant.">
        Détail par référence
      </SousTitre>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              {COLONNES.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={col.num ? "num" : undefined}
                  aria-sort={
                    tri.col === col.key ? (tri.asc ? "ascending" : "descending") : undefined
                  }
                >
                  <button className="th-sort" onClick={() => trier(col.key)}>
                    {col.label}
                    {tri.col === col.key && <span aria-hidden="true">{tri.asc ? " ↑" : " ↓"}</span>}
                  </button>
                </th>
              ))}
              <th scope="col">Dernière vente</th>
            </tr>
          </thead>
          <tbody>
            {produits.map((x) => (
              <tr key={x.id} className={x.active ? "" : "adm-row-off"}>
                <td>
                  <strong>{x.name}</strong>
                  <span className="cell-sub">{x.category}</span>
                </td>
                <td className="num">{num(x.views)}</td>
                <td className="num">{num(x.orders)}</td>
                <td className="num">{num(x.units)}</td>
                <td className="num">
                  <Conversion value={x.conversion} />
                </td>
                <td className="num">{eur(x.revenue_cents)}</td>
                <td className="num">{eur(x.price_cents)}</td>
                <td className="num">
                  {x.rating_count ? `${decimale(x.rating_avg, 2)} (${x.rating_count})` : "-"}
                </td>
                <td className="num">{x.stock}</td>
                <td>
                  {x.last_order_at ? (
                    fmtDate(x.last_order_at)
                  ) : (
                    <span className="adm-tag off">Jamais</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="viz-grid viz-grid-2 viz-spaced">
        <BarChart
          title="Chiffre d'affaires par catégorie"
          format={eur}
          data={data.categories.map((x) => ({ key: x.category, value: x.revenue_cents }))}
        />
        <BarChart
          title="Statut des commandes"
          format={num}
          data={data.statuses.map((s) => ({
            key: STATUS_LABELS[s.status] || s.status,
            value: s.count,
          }))}
        />
      </div>

      <SousTitre>Codes promo</SousTitre>
      {data.promos.length === 0 ? (
        <div className="viz-block viz-empty">Aucun code utilisé</div>
      ) : (
        <div className="wh-cadre">
          <table className="adm-table">
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col" className="num">
                  Commandes
                </th>
                <th scope="col" className="num">
                  CA généré
                </th>
                <th scope="col" className="num">
                  Remise consentie
                </th>
                <th scope="col" className="num">
                  Panier moyen
                </th>
              </tr>
            </thead>
            <tbody>
              {data.promos.map((x) => (
                <tr key={x.code}>
                  <td className="code">{x.code}</td>
                  <td className="num">{num(x.orders)}</td>
                  <td className="num">{eur(x.revenue_cents)}</td>
                  <td className="num">{eur(x.discount_cents)}</td>
                  <td className="num">{eur(Math.round(x.revenue_cents / x.orders))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <SousTitre>Meilleurs clients</SousTitre>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Client</th>
              <th scope="col">E-mail</th>
              <th scope="col">Ville</th>
              <th scope="col" className="num">
                Commandes
              </th>
              <th scope="col" className="num">
                Total dépensé
              </th>
            </tr>
          </thead>
          <tbody>
            {data.top_customers.map((x) => (
              <tr key={x.id}>
                <td>
                  <strong>{x.name}</strong>
                </td>
                <td>{x.email}</td>
                <td>{x.city || "-"}</td>
                <td className="num">{x.orders}</td>
                <td className="num">{eur(x.total_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
