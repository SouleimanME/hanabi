/** Boite a outils graphique du back-office.
 *
 * Ecrite a la main, sans bibliotheque : le projet n'en a pas et une dependance
 * de graphiques pese plus lourd que tout le reste du back-office reuni.
 *
 * Deux principes gouvernent ce fichier.
 *
 * **Les couleurs sont mesurees, pas choisies.** La palette de `palette.js` a ete
 * validee : bande de clarte, plancher de chroma, separation sous deuteranopie et
 * protanopie, contraste sur le fond. On ne juge pas ces criteres a l'oeil.
 *
 * **Le SVG est dessine a la taille reelle.** La version precedente etirait un
 * `viewBox` fixe avec `preserveAspectRatio="none"`, ce qui deforme les traits et
 * le texte des que le conteneur n'a pas les proportions prevues : les libelles
 * s'aplatissent, les traits changent d'epaisseur selon leur direction. On mesure
 * donc la largeur disponible et on dessine en pixels.
 */
import { useCallback, useId, useState } from "react";

import { axisNumber, niceTicks, smoothPath, useMeasuredWidth } from "./chart-utils.js";
import { CHART, SEQUENTIAL, SERIES } from "./palette.js";

/* ------------------------------------------------------------------ */
/* Habillage commun                                                   */
/* ------------------------------------------------------------------ */

/** Carte contenant un graphique, son titre et sa vue tableau. */
function ChartCard({ title, hint, legend, table, children }) {
  const [tableau, setTableau] = useState(false);
  return (
    <figure className="ch-card">
      <figcaption className="ch-head">
        <div>
          <span className="ch-title">{title}</span>
          {hint && <span className="ch-hint">{hint}</span>}
        </div>
        {table && (
          // Toute valeur doit rester atteignable sans survol ni couleur : c'est
          // la condition pour qu'un graphique reste accessible.
          <button
            type="button"
            className="ch-toggle"
            aria-pressed={tableau}
            onClick={() => setTableau((v) => !v)}
          >
            {tableau ? "Graphique" : "Tableau"}
          </button>
        )}
      </figcaption>
      {legend}
      {tableau && table ? <div className="ch-table-wrap">{table}</div> : children}
    </figure>
  );
}

/** Légende : indispensable dès deux séries, l'identité ne peut pas reposer
 *  sur la seule couleur. */
function Legend({ items }) {
  if (!items || items.length < 2) return null;
  return (
    <ul className="ch-legend">
      {items.map((item) => (
        <li key={item.label}>
          <span className="ch-swatch" style={{ background: item.color }} aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

/** Info-bulle suivant le pointeur, en HTML plutôt qu'en SVG : le texte y reste
 *  net et se met en forme avec les styles du reste de l'interface. */
function Tooltip({ x, y, width, children }) {
  if (x == null) return null;
  // Bascule à gauche du curseur quand on approche du bord droit.
  const aGauche = x > width * 0.62;
  return (
    <div className={"ch-tip" + (aGauche ? " left" : "")} style={{ left: x, top: y }} role="status">
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Courbes                                                            */
/* ------------------------------------------------------------------ */
const PAD = { top: 14, right: 16, bottom: 26, left: 52 };

/**
 * Courbe temporelle, une ou plusieurs séries.
 *
 * @param series [{ key, label, color, values: number[], dashed? }]
 * @param labels étiquettes de l'axe des abscisses
 * @param format mise en forme des valeurs dans l'info-bulle et l'axe
 */
export function LineChart({
  series,
  labels,
  format = axisNumber,
  formatTick,
  height = 210,
  hint,
  title,
}) {
  const [ref, width] = useMeasuredWidth();
  const [actif, setActif] = useState(null);
  const [survole, setSurvole] = useState(null);
  const gradId = useId();

  const plotW = Math.max(80, width - PAD.left - PAD.right);
  const plotH = height - PAD.top - PAD.bottom;
  // `null` marque un trou : une série qui ne couvre qu'une partie de la période
  // (le mesuré face au projeté) ne doit pas être tirée vers zéro.
  const definis = (s) => s.values.map((v, i) => ({ v, i })).filter((p) => p.v != null);
  const max = Math.max(...series.flatMap((s) => s.values.filter((v) => v != null)), 1);
  const ticks = niceTicks(max);
  const haut = ticks[ticks.length - 1] || max;

  const x = (i) => PAD.left + (labels.length > 1 ? (i * plotW) / (labels.length - 1) : plotW / 2);
  const y = (v) => PAD.top + plotH - (v / haut) * plotH;

  const surIndex = useCallback(
    (event) => {
      const rect = event.currentTarget.getBoundingClientRect();
      const rel = event.clientX - rect.left - PAD.left;
      const i = Math.round((rel / plotW) * (labels.length - 1));
      setActif(Math.max(0, Math.min(labels.length - 1, i)));
    },
    [plotW, labels.length],
  );

  const tick = formatTick || format;

  const table = (
    <table className="ch-table">
      <thead>
        <tr>
          <th>Période</th>
          {series.map((s) => (
            <th key={s.key}>{s.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {labels.map((l, i) => (
          <tr key={l}>
            <td>{l}</td>
            {series.map((s) => (
              <td key={s.key} className="mono">
                {s.values[i] == null ? "-" : format(s.values[i])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <ChartCard
      title={title}
      hint={hint}
      table={table}
      legend={<Legend items={series.map((s) => ({ label: s.label, color: s.color }))} />}
    >
      <div className="ch-plot" ref={ref}>
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={title}
          onMouseMove={surIndex}
          onMouseLeave={() => setActif(null)}
        >
          <defs>
            {series.map((s, i) => (
              <linearGradient key={s.key} id={`${gradId}-${i}`} x1="0" y1="0" x2="0" y2="1">
                {/* Lavis à 10 % : une aire pleine écraserait la courbe. */}
                <stop offset="0%" stopColor={s.color} stopOpacity="0.16" />
                <stop offset="100%" stopColor={s.color} stopOpacity="0" />
              </linearGradient>
            ))}
          </defs>

          {/* Grille : filets pleins d'un ton au-dessus du fond, jamais en
              pointillés, le pointillé se lisant comme un seuil. */}
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={PAD.left}
                x2={PAD.left + plotW}
                y1={y(t)}
                y2={y(t)}
                stroke={CHART.grid}
                strokeWidth="1"
              />
              <text x={PAD.left - 10} y={y(t) + 4} className="ch-axis" textAnchor="end">
                {tick(t)}
              </text>
            </g>
          ))}

          {series.map((s, i) => {
            const points = definis(s).map((p) => ({ x: x(p.i), y: y(p.v), i: p.i, v: p.v }));
            if (!points.length) return null;
            const chemin = smoothPath(points);
            const fin = points[points.length - 1];
            // Survol : la série pointée reste pleine, les autres s'effacent.
            // C'est ce qui permet de suivre une ligne dans un faisceau.
            const attenue = survole && survole !== s.key;
            return (
              <g
                key={s.key}
                className={"ch-serie" + (attenue ? " attenue" : "")}
                onMouseEnter={() => setSurvole(s.key)}
                onMouseLeave={() => setSurvole(null)}
              >
                {series.length === 1 && (
                  <path
                    d={`${chemin} L${fin.x},${y(0)} L${points[0].x},${y(0)} Z`}
                    fill={`url(#${gradId}-${i})`}
                    className="ch-aire"
                  />
                )}
                <path
                  d={chemin}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={survole === s.key ? 2.6 : 2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  strokeDasharray={s.dashed ? "6 5" : undefined}
                  className={s.dashed ? "ch-trait pointille" : "ch-trait"}
                />
                {/* Marqueur de fin seulement : un point sur chaque valeur
                    encombre sans rien apprendre. L'anneau de 2 px dans la
                    couleur du fond le garde lisible là où il croise un trait. */}
                <circle
                  cx={fin.x}
                  cy={fin.y}
                  r="4.5"
                  fill={s.color}
                  stroke={CHART.surface}
                  strokeWidth="2"
                  className="ch-fin"
                />
              </g>
            );
          })}

          {actif != null && (
            <g pointerEvents="none">
              <line
                x1={x(actif)}
                x2={x(actif)}
                y1={PAD.top}
                y2={PAD.top + plotH}
                stroke={CHART.crosshair}
                strokeWidth="1"
              />
              {series.map((s) =>
                s.values[actif] == null ? null : (
                  <circle
                    key={s.key}
                    cx={x(actif)}
                    cy={y(s.values[actif])}
                    r="4.5"
                    fill={s.color}
                    stroke={CHART.surface}
                    strokeWidth="2"
                  />
                ),
              )}
            </g>
          )}

          {labels.map((l, i) =>
            i % Math.ceil(labels.length / 6) === 0 ? (
              <text key={l} x={x(i)} y={height - 8} className="ch-axis" textAnchor="middle">
                {l}
              </text>
            ) : null,
          )}
        </svg>

        {actif != null && (
          <Tooltip x={x(actif)} y={PAD.top} width={width}>
            <div className="ch-tip-key">{labels[actif]}</div>
            {series.map((s) =>
              s.values[actif] == null ? null : (
                <div key={s.key} className="ch-tip-row">
                  <span className="ch-swatch" style={{ background: s.color }} aria-hidden="true" />
                  <span className="ch-tip-lbl">{s.label}</span>
                  <span className="mono">{format(s.values[actif])}</span>
                </div>
              ),
            )}
          </Tooltip>
        )}
      </div>
    </ChartCard>
  );
}

/* ------------------------------------------------------------------ */
/* Barres horizontales                                                */
/* ------------------------------------------------------------------ */

/**
 * Barres horizontales, série unique.
 *
 * Une seule couleur pour toutes les barres : colorer chacune différemment
 * réencoderait en teinte ce que la longueur dit déjà, et gaspillerait le seul
 * canal disponible pour l'identité.
 */
export function BarChart({
  data,
  title,
  hint,
  format = axisNumber,
  color = SERIES[0],
  height,
  onSelect,
  selected,
}) {
  const [actif, setActif] = useState(null);
  const max = Math.max(...data.map((d) => d.value), 1);

  const table = (
    <table className="ch-table">
      <thead>
        <tr>
          <th>Catégorie</th>
          <th>Valeur</th>
        </tr>
      </thead>
      <tbody>
        {data.map((d) => (
          <tr key={d.key}>
            <td>{d.key}</td>
            <td className="mono">{format(d.value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <ChartCard title={title} hint={hint} table={table}>
      <div className="ch-bars" style={height ? { minHeight: height } : undefined}>
        {data.map((d) => (
          // Ligne cliquable seulement si l'appelant en fait quelque chose :
          // un curseur en main sur un element inerte est une promesse non tenue.
          <div
            key={d.key}
            className={
              "ch-bar-row" +
              (actif === d.key ? " on" : "") +
              (onSelect ? " cliquable" : "") +
              (selected === d.key ? " choisi" : "")
            }
            onMouseEnter={() => setActif(d.key)}
            onMouseLeave={() => setActif(null)}
            onClick={onSelect ? () => onSelect(selected === d.key ? null : d.key) : undefined}
            onKeyDown={
              onSelect
                ? (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(selected === d.key ? null : d.key);
                    }
                  }
                : undefined
            }
            role={onSelect ? "button" : undefined}
            tabIndex={onSelect ? 0 : undefined}
            aria-pressed={onSelect ? selected === d.key : undefined}
          >
            <span className="ch-bar-key" title={d.key}>
              {d.key}
            </span>
            <span className="ch-bar-track">
              <span
                className="ch-bar-fill"
                style={{
                  width: `${Math.max(1, (d.value / max) * 100)}%`,
                  background: color,
                }}
              />
            </span>
            <span className="ch-bar-val mono">{format(d.value)}</span>
          </div>
        ))}
      </div>
    </ChartCard>
  );
}

/* ------------------------------------------------------------------ */
/* Répartition                                                        */
/* ------------------------------------------------------------------ */

/**
 * Part d'un tout, en anneau.
 *
 * Réservé aux répartitions lisibles d'un coup d'oeil : six segments au plus, et
 * jamais pour comparer des valeurs proches : un anneau ne permet pas de dire
 * lequel de deux arcs presque egaux est le plus grand. Un écart de 2 px dans la
 * couleur du fond sépare les segments, plutôt qu'un contour : un trait ajouterait
 * de l'encre qui n'est pas de la donnée.
 */
export function DonutChart({
  data,
  title,
  hint,
  format = axisNumber,
  total: totalLabel,
  onSelect,
  selected,
}) {
  const [actif, setActif] = useState(null);
  const total = data.reduce((s, d) => s + d.value, 0) || 1;

  const R = 62;
  const STROKE = 20;
  const CX = 78;
  const CY = 78;
  const circ = 2 * Math.PI * R;
  // Écart de 2 px, exprimé en longueur d'arc.
  const gap = 2;

  let offset = 0;
  const arcs = data.map((d, i) => {
    const longueur = Math.max(0, (d.value / total) * circ - gap);
    const arc = { ...d, longueur, offset, color: SERIES[i % SERIES.length] };
    offset += (d.value / total) * circ;
    return arc;
  });

  const table = (
    <table className="ch-table">
      <thead>
        <tr>
          <th>Segment</th>
          <th>Valeur</th>
          <th>Part</th>
        </tr>
      </thead>
      <tbody>
        {arcs.map((a) => (
          <tr key={a.key}>
            <td>{a.key}</td>
            <td className="mono">{format(a.value)}</td>
            <td className="mono">{((a.value / total) * 100).toFixed(1)} %</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <ChartCard title={title} hint={hint} table={table}>
      <div className="ch-donut">
        <svg width="156" height="156" viewBox="0 0 156 156" role="img" aria-label={title}>
          {arcs.map((a) => (
            <circle
              key={a.key}
              cx={CX}
              cy={CY}
              r={R}
              fill="none"
              stroke={a.color}
              strokeWidth={actif === a.key ? STROKE + 4 : STROKE}
              strokeDasharray={`${a.longueur} ${circ - a.longueur}`}
              strokeDashoffset={-a.offset + circ / 4}
              onMouseEnter={() => setActif(a.key)}
              onMouseLeave={() => setActif(null)}
              style={{ transition: "stroke-width .15s ease" }}
            />
          ))}
          <text x={CX} y={CY - 2} textAnchor="middle" className="ch-donut-total">
            {totalLabel ?? format(total)}
          </text>
          <text x={CX} y={CY + 16} textAnchor="middle" className="ch-donut-sub">
            total
          </text>
        </svg>

        <ul className="ch-donut-legend">
          {arcs.map((a) => (
            <li
              key={a.key}
              className={
                (actif === a.key ? "on" : "") +
                (onSelect ? " cliquable" : "") +
                (selected === a.key ? " choisi" : "")
              }
              onMouseEnter={() => setActif(a.key)}
              onMouseLeave={() => setActif(null)}
              onClick={onSelect ? () => onSelect(selected === a.key ? null : a.key) : undefined}
              role={onSelect ? "button" : undefined}
              tabIndex={onSelect ? 0 : undefined}
              aria-pressed={onSelect ? selected === a.key : undefined}
            >
              <span className="ch-swatch" style={{ background: a.color }} aria-hidden="true" />
              <span className="ch-donut-key">{a.key}</span>
              <span className="mono ch-donut-val">{format(a.value)}</span>
              <span className="mono ch-donut-pct">{((a.value / total) * 100).toFixed(0)} %</span>
            </li>
          ))}
        </ul>
      </div>
    </ChartCard>
  );
}

/* ------------------------------------------------------------------ */
/* Carte de chaleur                                                   */
/* ------------------------------------------------------------------ */

/** Échelle de la carte de chaleur : sans elle, la couleur ne se traduit pas. */
export function HeatScale({ max, format = (v) => `${(v * 100).toFixed(0)} %` }) {
  return (
    <div className="ch-scale">
      <span className="ch-scale-lbl">0</span>
      {SEQUENTIAL.map((c) => (
        <span key={c} className="ch-scale-step" style={{ background: c }} />
      ))}
      <span className="ch-scale-lbl">{format(max)}</span>
    </div>
  );
}
