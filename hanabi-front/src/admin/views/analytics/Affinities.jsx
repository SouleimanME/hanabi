/** Analyse de panier : paires achetees ensemble plus souvent que le hasard. */
import { decimale, num, pct } from "../../format.js";
import { SousTitre } from "../../ui.jsx";

export function Affinities({ data }) {
  if (!data.pairs.length) {
    return (
      <div className="viz-block viz-empty">
        Pas assez de commandes communes pour dégager une règle fiable (seuil :{" "}
        {num(data.min_support_orders)} commandes).
      </div>
    );
  }

  const maxLift = Math.max(...data.pairs.map((p) => p.lift), 1);

  return (
    <div>
      <SousTitre
        note={`Calculé sur ${num(data.orders)} commandes, avec au moins ${num(data.min_support_orders)} commandes communes. Au-dessus d'un lift de 1, les deux articles partent ensemble plus souvent que le hasard ; en dessous, ils se substituent. La confiance seule se laisse tromper par les best-sellers.`}
      >
        Produits achetés ensemble
      </SousTitre>

      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Association</th>
              <th scope="col" className="num">
                Commandes communes
              </th>
              <th scope="col" className="num">
                Support
              </th>
              <th scope="col" className="num">
                Confiance A→B
              </th>
              <th scope="col" className="num">
                Confiance B→A
              </th>
              <th scope="col">Lift</th>
            </tr>
          </thead>
          <tbody>
            {data.pairs.map((p) => (
              <tr key={`${p.a_id}-${p.b_id}`}>
                <td>
                  <strong>{p.a_name}</strong>
                  <span className="cell-sub">+ {p.b_name}</span>
                </td>
                <td className="num">{num(p.orders_together)}</td>
                <td className="num">{pct(p.support)}</td>
                <td className="num">{pct(p.confidence_ab)}</td>
                <td className="num">{pct(p.confidence_ba)}</td>
                <td>
                  <div className="lift-cell">
                    <span className="lift-bar" aria-hidden="true">
                      <span
                        className={"lift-fill" + (p.lift >= 1 ? " up" : "")}
                        style={{ width: `${Math.round((p.lift / maxLift) * 100)}%` }}
                      />
                    </span>
                    <span className={"num lift-val" + (p.lift >= 1 ? " up" : "")}>
                      ×{decimale(p.lift, 2)}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="adm-legend">
        Usage direct : proposer B sur la fiche de A, composer une offre groupée, ou rapprocher les
        deux références dans le catalogue.
      </p>
    </div>
  );
}
