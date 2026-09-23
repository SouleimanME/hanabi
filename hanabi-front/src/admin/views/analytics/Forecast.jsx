/** Tendance du chiffre d'affaires et saisonnalite. */
import { decimale, eur, pct } from "../../format.js";
import { axisEuro } from "../../chart-utils.js";
import { BarChart, LineChart } from "../../charts.jsx";
import { SERIES } from "../../palette.js";
import { SousTitre } from "../../ui.jsx";

const MOIS_COURTS = [
  "janv.",
  "févr.",
  "mars",
  "avr.",
  "mai",
  "juin",
  "juil.",
  "août",
  "sept.",
  "oct.",
  "nov.",
  "déc.",
];

export function Forecast({ data }) {
  if (!data.trend) {
    return <div className="viz-block viz-empty">Pas encore assez d&apos;historique</div>;
  }

  const t = data.trend;
  // Mesure et projection sur la meme courbe ; le dernier point mesure sert de
  // charniere pour que la projection prolonge la courbe au lieu de flotter.
  const serie = [
    ...data.history.map((m, i) => ({
      ...m,
      projete: false,
      charniere: i === data.history.length - 1,
    })),
    ...data.projection.map((m) => ({ ...m, projete: true, charniere: false })),
  ];
  const derniere = data.projection[data.projection.length - 1];

  const cartes = [
    {
      label: "Progression par mois",
      value: eur(t.slope_cents_per_month),
      hint: `De ${t.from} à ${t.to}`,
    },
    {
      label: "Coefficient de détermination",
      value: decimale(t.r2, 3),
      hint:
        t.r2 >= 0.9
          ? "Tendance très régulière"
          : t.r2 >= 0.7
            ? "Tendance nette"
            : "Trop irrégulier pour projeter",
    },
    {
      label: "Croissance mensuelle composée",
      value: data.cmgr == null ? "-" : pct(data.cmgr),
      hint: "Lissée sur toute la période",
    },
    {
      label: `Projection ${derniere?.month ?? ""}`,
      value: eur(derniere?.revenue_cents ?? 0),
      hint: "Si la tendance se poursuit",
    },
  ];

  return (
    <div>
      <SousTitre
        note={`Droite des moindres carrés sur ${data.history.length} mois, prolongée de ${data.horizon} mois. Sous un R² de 0,7, la projection ne vaut pas grand-chose.`}
      >
        Tendance du chiffre d&apos;affaires
      </SousTitre>
      <dl className="adm-cards adm-cards-4">
        {cartes.map((carte) => (
          <div key={carte.label} className="adm-card">
            <dt className="adm-card-lbl">{carte.label}</dt>
            <dd className="adm-card-val num">{carte.value}</dd>
            <dd className="adm-card-hint">{carte.hint}</dd>
          </div>
        ))}
      </dl>

      <div className="viz-grid viz-grid-1">
        <LineChart
          title="Chiffre d'affaires mensuel"
          hint="la projection prolonge la droite de tendance"
          height={260}
          labels={serie.map((m) => m.month.slice(2))}
          format={eur}
          formatTick={axisEuro}
          series={[
            {
              key: "mesure",
              label: "Mesuré",
              color: SERIES[0],
              values: serie.map((m) => (m.projete ? null : m.revenue_cents)),
            },
            {
              key: "projete",
              label: "Projeté",
              color: SERIES[1],
              dashed: true,
              values: serie.map((m) => (m.projete || m.charniere ? m.revenue_cents : null)),
            },
          ]}
        />
      </div>

      <SousTitre note="Chaque mois calendaire rapporté à la moyenne (100). Sur douze mois d'historique, chaque mois n'est observé qu'une fois : l'indice devient fiable au-delà de deux ans.">
        Saisonnalité
      </SousTitre>
      <BarChart
        title="Indice par mois"
        hint="100 = mois moyen"
        format={(v) => String(v)}
        data={data.seasonality.map((s) => ({
          key: MOIS_COURTS[s.month - 1],
          value: Math.round(s.index * 100),
        }))}
      />
    </div>
  );
}
