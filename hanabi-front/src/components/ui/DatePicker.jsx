/** Date de naissance en trois listes natives. */
import { ChevronDown } from "lucide-react";
import { useT } from "../../i18n/context.jsx";

function nomsDesMois() {
  const langue = document.documentElement.lang || "fr";
  const format = new Intl.DateTimeFormat(langue, { month: "long" });
  return Array.from({ length: 12 }, (_, i) => format.format(new Date(2000, i, 1)));
}

function Liste({ label, value, onChange, options }) {
  return (
    <span className="select">
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{label}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown size={16} aria-hidden="true" />
    </span>
  );
}

export function DatePicker({ value, onChange }) {
  const t = useT();
  const [y = "", m = "", d = ""] = value ? value.split("-") : [];
  const poser = (annee, mois, jour) => onChange([annee, mois, jour].join("-"));

  const anneeCourante = new Date().getFullYear();
  const annees = Array.from({ length: 100 }, (_, i) => String(anneeCourante - 16 - i));
  const mois = nomsDesMois().map((label, i) => ({ value: String(i + 1).padStart(2, "0"), label }));
  const joursDansMois = m && y ? new Date(Number(y), Number(m), 0).getDate() : 31;
  const jours = Array.from({ length: joursDansMois }, (_, i) => String(i + 1).padStart(2, "0"));

  return (
    <fieldset className="field date-field">
      <legend>{t("birthdate")}</legend>
      <div className="date-row">
        <Liste
          label={t("day")}
          value={d}
          onChange={(v) => poser(y, m, v)}
          options={jours.map((v) => ({ value: v, label: String(Number(v)) }))}
        />
        <Liste label={t("month")} value={m} onChange={(v) => poser(y, v, d)} options={mois} />
        <Liste
          label={t("year")}
          value={y}
          onChange={(v) => poser(v, m, d)}
          options={annees.map((v) => ({ value: v, label: v }))}
        />
      </div>
    </fieldset>
  );
}
