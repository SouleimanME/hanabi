/** Rentabilite : marge brute, classement ABC, ruptures a venir. */
import { decimale, eur, num, pct } from "../../format.js";
import { SousTitre } from "../../ui.jsx";

const ABC_HINTS = {
  A: "Les références qui produisent les 80 premiers pour cent de la marge. Jamais en rupture.",
  B: "Les 15 pour cent suivants. Réapprovisionnement normal.",
  C: "Le solde. Candidats à la sortie du catalogue si le stock coûte à porter.",
};

export function Profitability({ data }) {
  const p = data.profitability;
  const produits = [...data.products].sort((a, b) => b.margin_cents - a.margin_cents);
  const maxMarge = Math.max(...produits.map((x) => x.margin_cents), 1);
  const c = data.correlation;

  const cartes = [
    { label: "Marge dégagée", value: eur(p.margin_cents) },
    {
      label: "Taux de marge",
      value: pct(p.margin_rate),
      hint: `Sur ${eur(p.revenue_cents)} de ventes`,
    },
    {
      label: "Ruptures sous 21 jours",
      value: num(p.at_risk.length),
      hint: "Au rythme des 90 derniers jours",
    },
    {
      label: "Corrélation vues / ventes",
      value: c.views_units == null ? "-" : decimale(c.views_units, 2),
      hint: "1 : l'audience se transforme ; 0 : le frein est ailleurs",
    },
  ];

  return (
    <div>
      <SousTitre note="Calculée sur le prix et le coût figés dans chaque ligne de commande : un nouveau tarif fournisseur ne réécrit pas les mois clos.">
        Marge brute
      </SousTitre>
      <dl className="adm-cards adm-cards-4">
        {cartes.map((carte) => (
          <div key={carte.label} className="adm-card">
            <dt className="adm-card-lbl">{carte.label}</dt>
            <dd className="adm-card-val num">{carte.value}</dd>
            {carte.hint && <dd className="adm-card-hint">{carte.hint}</dd>}
          </div>
        ))}
      </dl>

      <SousTitre note="Trié sur la marge et non sur le chiffre d'affaires : c'est elle qui paie les charges.">
        Classement ABC
      </SousTitre>
      <div className="abc-grid">
        {p.abc.map((classe) => (
          <div key={classe.classe} className={`abc-card abc-${classe.classe}`}>
            <div className="abc-head">
              <strong>Classe {classe.classe}</strong>
              <span className="num">{classe.references} réf.</span>
            </div>
            <div className="abc-val num">{eur(classe.margin_cents)}</div>
            <p className="segment-hint">{ABC_HINTS[classe.classe]}</p>
          </div>
        ))}
      </div>

      <SousTitre>Marge par référence</SousTitre>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Produit</th>
              <th scope="col">Classe</th>
              <th scope="col" className="num">
                Prix
              </th>
              <th scope="col" className="num">
                Coût
              </th>
              <th scope="col" className="num">
                Marge unitaire
              </th>
              <th scope="col" className="num">
                Unités
              </th>
              <th scope="col">Marge totale</th>
              <th scope="col" className="num">
                Taux
              </th>
              <th scope="col" className="num">
                Part cumulée
              </th>
              <th scope="col" className="num">
                Stock
              </th>
            </tr>
          </thead>
          <tbody>
            {produits.map((x) => (
              <tr key={x.id}>
                <td>
                  <strong>{x.name}</strong>
                  <span className="cell-sub">{x.category}</span>
                </td>
                <td>
                  <span className={`abc-tag abc-${x.abc}`}>{x.abc}</span>
                </td>
                <td className="num">{eur(x.price_cents)}</td>
                <td className="num">{x.cost_cents ? eur(x.cost_cents) : "-"}</td>
                <td className="num">{x.cost_cents ? eur(x.unit_margin_cents) : "-"}</td>
                <td className="num">{num(x.units)}</td>
                <td>
                  <span className="marge-cell">
                    <span className="marge-bar" aria-hidden="true">
                      <span
                        className="marge-fill"
                        style={{ width: `${Math.round((x.margin_cents / maxMarge) * 100)}%` }}
                      />
                    </span>
                    <span className="num">{eur(x.margin_cents)}</span>
                  </span>
                </td>
                <td className="num">{x.margin_rate ? pct(x.margin_rate) : "-"}</td>
                <td className="num">{pct(x.cumulative_share)}</td>
                <td className="num">{x.stock}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SousTitre note="Un écart positif signale un article qui fait du volume sans rapporter ; un écart négatif, une référence discrète qui porte le résultat.">
        Ce que le classement par marge change
      </SousTitre>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Produit</th>
              <th scope="col" className="num">
                Rang au CA
              </th>
              <th scope="col" className="num">
                Rang à la marge
              </th>
              <th scope="col" className="num">
                Écart
              </th>
              <th scope="col" className="num">
                Taux de marge
              </th>
            </tr>
          </thead>
          <tbody>
            {p.rank_shifts.map((r) => (
              <tr key={r.name}>
                <td>
                  <strong>{r.name}</strong>
                </td>
                <td className="num">#{r.revenue_rank}</td>
                <td className="num">#{r.margin_rank}</td>
                <td className="num">
                  <span
                    className={
                      "delta " +
                      (r.shift > 0 ? "delta-up" : r.shift < 0 ? "delta-down" : "delta-none")
                    }
                  >
                    {r.shift > 0 ? `+${r.shift}` : r.shift || "="}
                  </span>
                </td>
                <td className="num">{r.margin_rate ? pct(r.margin_rate) : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {p.at_risk.length > 0 && (
        <>
          <SousTitre note="Jours de vente que le stock couvre encore, au rythme des 90 derniers jours.">
            Ruptures à venir
          </SousTitre>
          <div className="wh-cadre">
            <table className="adm-table">
              <thead>
                <tr>
                  <th scope="col">Produit</th>
                  <th scope="col" className="num">
                    Stock
                  </th>
                  <th scope="col" className="num">
                    Ventes par jour
                  </th>
                  <th scope="col" className="num">
                    Couverture
                  </th>
                </tr>
              </thead>
              <tbody>
                {p.at_risk.map((a) => (
                  <tr key={a.name}>
                    <td>
                      <strong>{a.name}</strong>
                    </td>
                    <td className="num">{a.stock}</td>
                    <td className="num">{a.daily_velocity}</td>
                    <td className="num">
                      <span className={"conv " + (a.days_of_stock < 7 ? "conv-low" : "conv-mid")}>
                        {a.days_of_stock} j
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
