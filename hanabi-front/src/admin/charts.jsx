/** Graphiques du back-office, en SVG ecrit a la main. */
import { useCallback, useId, useState } from "react";

import { axisNumber, niceTicks, smoothPath, useMeasuredWidth } from "./chart-utils.js";
import { pct } from "./format.js";
import { CHART, SEQUENTIAL, SERIES } from "./palette.js";

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

/** Legende des qu'il y a deux series : l'identite ne repose pas sur la couleur. */
function Legend({ items }) {
  if (!items || items.length < 2) return null;
  return (
    <ul className="ch-legend">
      {items.map((item) => (
        <li key={item.label}>
          <span
            className={"ch-swatch" + (item.dashed ? " pointille" : "")}
            style={{ "--swatch": item.color }}
            aria-hidden="true"
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function Tooltip({ x, y, width, children }) {
  if (x == null) return null;
  return (
    <div
      className={"ch-tip" + (x > width * 0.62 ? " left" : "")}
      style={{ left: x, top: y }}
      role="status"
    >
      {children}
    </div>
  );
}

const PAD = { top: 14, right: 16, bottom: 26, left: 52 };

/** Courbe temporelle.
 * @param series [{ key, label, color, values: (number|null)[], dashed? }] ;
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
  const aide = useId();

  const plotW = Math.max(80, width - PAD.left - PAD.right);
  const plotH = height - PAD.top - PAD.bottom;
  const definis = (s) => s.values.map((v, i) => ({ v, i })).filter((p) => p.v != null);
  const max = Math.max(...series.flatMap((s) => s.values.filter((v) => v != null)), 1);
  const ticks = niceTicks(max);
  const haut = ticks[ticks.length - 1] || max;

  const x = (i) => PAD.left + (labels.length > 1 ? (i * plotW) / (labels.length - 1) : plotW / 2);
  const y = (v) => PAD.top + plotH - (v / haut) * plotH;

  const borner = useCallback((i) => Math.max(0, Math.min(labels.length - 1, i)), [labels.length]);

  const surIndex = useCallback(
    (event) => {
      const rect = event.currentTarget.getBoundingClientRect();
      const i = Math.round(((event.clientX - rect.left - PAD.left) / plotW) * (labels.length - 1));
      setActif(borner(i));
    },
    [plotW, labels.length, borner],
  );

  // La souris suit le survol ; le doigt et le stylet demandent un contact
  const surPointeur = useCallback(
    (event) => {
      if (event.pointerType === "mouse" || event.buttons > 0) surIndex(event);
    },
    [surIndex],
  );

  // Au clavier, le repere part du dernier point et se deplace d'un pas
  const surTouche = useCallback(
    (event) => {
      const dernier = labels.length - 1;
      const pas = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
      if (event.key === "Escape") {
        setActif(null);
        return;
      }
      if (pas) setActif((a) => borner((a == null ? dernier : a) + pas));
      else if (event.key === "Home") setActif(0);
      else if (event.key === "End") setActif(dernier);
      else return;
      event.preventDefault();
    },
    [labels.length, borner],
  );

  const tick = formatTick || format;

  const table = (
    <table className="ch-table">
      <thead>
        <tr>
          <th scope="col">Période</th>
          {series.map((s) => (
            <th key={s.key} scope="col">
              {s.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {labels.map((l, i) => (
          <tr key={l}>
            <th scope="row">{l}</th>
            {series.map((s) => (
              <td key={s.key} className="num">
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
      legend={
        <Legend items={series.map((s) => ({ label: s.label, color: s.color, dashed: s.dashed }))} />
      }
    >
      <div className="ch-plot" ref={ref}>
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={title}
          aria-describedby={aide}
          tabIndex={0}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture?.(event.pointerId);
            surIndex(event);
          }}
          onPointerMove={surPointeur}
          onPointerLeave={(event) => {
            if (event.pointerType === "mouse") setActif(null);
          }}
          onKeyDown={surTouche}
          onBlur={() => setActif(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={PAD.left + plotW} y1={y(t)} y2={y(t)} stroke={CHART.grid} />
              <text x={PAD.left - 10} y={y(t) + 4} className="ch-axis" textAnchor="end">
                {tick(t)}
              </text>
            </g>
          ))}

          {series.map((s) => {
            const points = definis(s).map((p) => ({ x: x(p.i), y: y(p.v) }));
            if (!points.length) return null;
            const chemin = smoothPath(points);
            const fin = points[points.length - 1];
            return (
              <g key={s.key}>
                {series.length === 1 && (
                  <path
                    d={`${chemin} L${fin.x},${y(0)} L${points[0].x},${y(0)} Z`}
                    fill={s.color}
                    fillOpacity="0.08"
                  />
                )}
                <path
                  d={chemin}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  strokeDasharray={s.dashed ? "6 5" : undefined}
                />
                <circle
                  cx={fin.x}
                  cy={fin.y}
                  r="4.5"
                  fill={s.color}
                  stroke={CHART.surface}
                  strokeWidth="2"
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
                  <span className="ch-swatch" style={{ "--swatch": s.color }} aria-hidden="true" />
                  <span className="ch-tip-lbl">{s.label}</span>
                  <span className="num">{format(s.values[actif])}</span>
                </div>
              ),
            )}
          </Tooltip>
        )}
        <span className="sr-only" id={aide}>
          Flèches gauche et droite pour lire les points un par un, Origine et Fin pour les extrêmes,
          Échap pour quitter.
        </span>
      </div>
    </ChartCard>
  );
}

/** Barres horizontales, une seule couleur : la longueur dit la valeur, le libelle dit l'identite. */
export function BarChart({
  data,
  title,
  hint,
  format = axisNumber,
  color = SERIES[0],
  onSelect,
  selected,
}) {
  const max = Math.max(...data.map((d) => d.value), 1);
  const total = data.reduce((s, d) => s + d.value, 0);

  const table = (
    <table className="ch-table">
      <thead>
        <tr>
          <th scope="col">Libellé</th>
          <th scope="col">Valeur</th>
          <th scope="col">Part</th>
        </tr>
      </thead>
      <tbody>
        {data.map((d) => (
          <tr key={d.key}>
            <th scope="row">{d.key}</th>
            <td className="num">{format(d.value)}</td>
            <td className="num">{total ? pct(d.value / total) : "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  const Ligne = onSelect ? "button" : "div";

  return (
    <ChartCard title={title} hint={hint} table={table}>
      <div className="ch-bars">
        {data.map((d) => (
          <Ligne
            key={d.key}
            type={onSelect ? "button" : undefined}
            className={
              "ch-bar-row" + (onSelect ? " cliquable" : "") + (selected === d.key ? " choisi" : "")
            }
            onClick={onSelect ? () => onSelect(selected === d.key ? null : d.key) : undefined}
            aria-pressed={onSelect ? selected === d.key : undefined}
          >
            <span className="ch-bar-key" title={d.key}>
              {d.key}
            </span>
            <span className="ch-bar-track" aria-hidden="true">
              <span
                className="ch-bar-fill"
                style={{ width: `${Math.max(1, (d.value / max) * 100)}%`, background: color }}
              />
            </span>
            <span className="ch-bar-val num">{format(d.value)}</span>
          </Ligne>
        ))}
      </div>
    </ChartCard>
  );
}

/** Legende de la carte de chaleur. */
export function HeatScale({ max, format = (v) => pct(v, 0) }) {
  return (
    <div className="ch-scale" aria-hidden="true">
      <span className="ch-scale-lbl">0</span>
      {SEQUENTIAL.map((c) => (
        <span key={c} className="ch-scale-step" style={{ background: c }} />
      ))}
      <span className="ch-scale-lbl">{format(max)}</span>
    </div>
  );
}
