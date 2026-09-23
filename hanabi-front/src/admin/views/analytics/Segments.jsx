/** Segmentation RFM : recence, frequence, montant, notes de 1 a 5. */
import { decimale, eur, num, pct } from "../../format.js";
import { SousTitre } from "../../ui.jsx";

const SEGMENT_HINTS = {
  Champions: "Récents, fréquents, gros paniers. À fidéliser en priorité.",
  Fideles: "Reviennent régulièrement sans être les plus gros acheteurs.",
  Prometteurs: "Achat récent, historique encore mince. À convertir en habitués.",
  Nouveaux: "Une seule commande, récente. Le second achat est l'enjeu.",
  "A risque": "Bons clients qui ne sont pas revenus. La relance a le plus de valeur ici.",
  "A reactiver": "Anciens acheteurs modestes, silencieux depuis longtemps.",
  Endormis: "Une commande ancienne et sans suite. Relance rarement rentable.",
};

/* Les segments arrivent du serveur sans accents : ce sont des cles */
const SEGMENT_LIBELLES = {
  Fideles: "Fidèles",
  "A risque": "À risque",
  "A reactiver": "À réactiver",
};
const libelle = (s) => SEGMENT_LIBELLES[s] || s;

export function Segments({ data }) {
  if (!data.segments.length) {
    return (
      <div className="viz-block viz-empty">Aucun acheteur à segmenter pour l&apos;instant</div>
    );
  }

  const maxClients = Math.max(...data.segments.map((s) => s.customers));

  return (
    <div>
      <SousTitre
        note={`Chaque acheteur est noté de 1 à 5 sur sa récence, sa fréquence et son montant, relativement aux autres. ${num(data.non_buyers)} inscrits n'ont jamais commandé et sont exclus du calcul.`}
      >
        Segmentation RFM
      </SousTitre>

      <ul className="segment-grid">
        {data.segments.map((s) => (
          <li key={s.segment} className="segment-card">
            <div className="segment-head">
              <strong>{libelle(s.segment)}</strong>
              <span className="num segment-count">{num(s.customers)}</span>
            </div>
            <div className="segment-bar" aria-hidden="true">
              <span
                className="segment-fill"
                style={{ width: `${Math.round((s.customers / maxClients) * 100)}%` }}
              />
            </div>
            <div className="segment-stats">
              <span>
                {pct(s.share)} des acheteurs · <strong>{pct(s.revenue_share)} du CA</strong>
              </span>
              <span>
                {eur(s.avg_value_cents)} en moyenne ·{" "}
                {`${decimale(s.avg_orders, s.avg_orders % 1 ? 2 : 0)} commande${s.avg_orders > 1 ? "s" : ""}`}{" "}
                · vu il y a {`${num(s.avg_recency_days)}\u00a0j`}
              </span>
            </div>
            <p className="segment-hint">{SEGMENT_HINTS[s.segment]}</p>
          </li>
        ))}
      </ul>

      <SousTitre note="Les trois plus gros contributeurs de chaque segment. « 555 » désigne le meilleur quintile sur les trois axes.">
        Exemples
      </SousTitre>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Segment</th>
              <th scope="col">Client</th>
              <th scope="col">Ville</th>
              <th scope="col">Scores</th>
              <th scope="col" className="num">
                Dernier achat
              </th>
              <th scope="col" className="num">
                Commandes
              </th>
              <th scope="col" className="num">
                Total dépensé
              </th>
            </tr>
          </thead>
          <tbody>
            {data.examples.map((e) => (
              <tr key={`${e.segment}-${e.email}`}>
                <td>{libelle(e.segment)}</td>
                <td>
                  <strong>{e.name}</strong>
                  <span className="cell-sub">{e.email}</span>
                </td>
                <td>{e.city || "-"}</td>
                <td className="code">{e.scores}</td>
                <td className="num">il y a {`${num(e.recency_days)}\u00a0j`}</td>
                <td className="num">{e.frequency}</td>
                <td className="num">{eur(e.monetary_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
