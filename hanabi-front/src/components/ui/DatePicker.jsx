/** Saisie d'une date de naissance via trois listes deroulantes.
 *
 * Choix delibere face a <input type="date"> : rendu identique sur tous les
 * navigateurs, et bien plus rapide pour remonter de plusieurs decennies.
 */
import { useT } from "../../i18n/context.jsx";
import { Dropdown } from "./Dropdown.jsx";

export function DatePicker({ value, onChange }) {
  const t = useT();
  const MONTHS = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
  ];
  const parts = value ? value.split("-") : ["", "", ""];
  const [y, m, d] = parts;
  const setY = (v) => onChange([v, m, d].join("-"));
  const setM = (v) => onChange([y, v, d].join("-"));
  const setD = (v) => onChange([y, m, v].join("-"));
  const curYear = new Date().getFullYear();
  const years = Array.from({ length: 100 }, (_, i) => String(curYear - 16 - i));
  const months = MONTHS.map((lbl, i) => ({ value: String(i + 1).padStart(2, "0"), label: lbl }));
  const daysInMonth = m && y ? new Date(parseInt(y), parseInt(m), 0).getDate() : 31;
  const days = Array.from({ length: daysInMonth }, (_, i) => String(i + 1).padStart(2, "0"));
  return (
    <div className="datepick">
      <span className="field-lbl">{t("birthdate")}</span>
      <div className="datepick-col">
        <Dropdown
          value={d || ""}
          onChange={setD}
          options={[{ value: "", label: t("day") }, ...days.map((v) => ({ value: v, label: v }))]}
        />
        <Dropdown
          value={m || ""}
          onChange={setM}
          options={[{ value: "", label: t("month") }, ...months]}
        />
        <Dropdown
          value={y || ""}
          onChange={setY}
          options={[{ value: "", label: t("year") }, ...years.map((v) => ({ value: v, label: v }))]}
        />
      </div>
    </div>
  );
}
