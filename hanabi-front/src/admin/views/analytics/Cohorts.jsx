/** Retention par cohorte d'inscription : une ligne par mois de creation, une
 *  colonne par mois ecoule. */
import { decimale, num } from "../../format.js";
import { heatColor, heatStep } from "../../chart-utils.js";
import { HeatScale } from "../../charts.jsx";
import { SousTitre } from "../../ui.jsx";

export function Cohorts({ data }) {
  const colonnes = data.rows[0]?.cells.length || 0;
  // Echelle calee hors mois 0, toujours le plus fort, qui ecraserait le reste
  const max = Math.max(
    ...data.rows.flatMap((r) =>
      r.cells
        .slice(1)
        .filter(Boolean)
        .map((c) => c.rate),
    ),
    0.01,
  );

  return (
    <div>
      <SousTitre note="M0 mesure la conversion à l'inscription, les colonnes suivantes la fidélisation. Une case vide est un mois pas encore advenu pour la cohorte, ce qui n'est pas un zéro.">
        Rétention par cohorte d&apos;inscription
      </SousTitre>

      <div className="wh-cadre">
        <table className="cohort-table">
          <caption className="sr-only">
            Pourcentage de chaque cohorte encore active, mois par mois
          </caption>
          <thead>
            <tr>
              <th scope="col">Cohorte</th>
              <th scope="col" className="num">
                Taille
              </th>
              {Array.from({ length: colonnes }, (_, i) => (
                <th key={i} scope="col" className="num">
                  M{i}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((ligne) => (
              <tr key={ligne.cohort}>
                <th scope="row" className="code cohort-key">
                  {ligne.cohort}
                </th>
                <td className="num cohort-size">{num(ligne.size)}</td>
                {ligne.cells.map((cell, i) =>
                  cell === null ? (
                    <td key={i} className="cohort-cell empty" />
                  ) : (
                    <td
                      key={i}
                      className="cohort-cell num"
                      data-fonce={heatStep(cell.rate, max) >= 3 || undefined}
                      style={{ background: heatColor(cell.rate, max) }}
                      title={`${num(cell.active)} client(s) actif(s) sur ${num(ligne.size)}`}
                    >
                      {cell.rate > 0 ? decimale(cell.rate * 100) : "-"}
                    </td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <HeatScale max={max} />
      <p className="adm-legend">
        Valeurs en pourcentage de la cohorte. Plus une case se rapproche du fond, moins la cohorte
        est active ce mois-là.
      </p>
    </div>
  );
}
