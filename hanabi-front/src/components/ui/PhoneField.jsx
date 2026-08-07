/** Champ telephone : indicatif pays a drapeau + numero national.
 *
 * Composant non controle : il detient l'indicatif et le numero, et remonte
 * au parent la chaine complete ("+33 6 12 34 56 78") via `onChange`. Le parent
 * n'a donc pas de valeur a repousser vers le bas.
 */
import { useState, useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";
import { DIAL_CODES } from "../../lib/dialCodes.js";

export function PhoneField({ onChange, label }) {
  const [selected, setSelected] = useState(DIAL_CODES[0]);
  const [num, setNum] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // `onChange` est garde dans une ref : le parent le recree a chaque rendu,
  // l'inclure dans les dependances relancerait l'effet en boucle.
  const notify = useRef(onChange);
  notify.current = onChange;

  useEffect(() => {
    const fn = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  useEffect(() => {
    notify.current(selected.dial + " " + num);
  }, [selected, num]);

  return (
    <div className="field">
      <span>{label}</span>
      <div className="phone-wrap" ref={ref}>
        <button type="button" className="phone-dial" onClick={() => setOpen((s) => !s)}>
          <img
            src={`https://flagcdn.com/24x18/${selected.code.toLowerCase()}.png`}
            alt={selected.label}
            className="phone-flag-img"
            width="24"
            height="18"
          />
          <span className="phone-code mono">{selected.dial}</span>
          <ChevronDown
            size={12}
            style={{
              color: "var(--muted)",
              flexShrink: 0,
              transform: open ? "rotate(180deg)" : "none",
              transition: ".2s",
            }}
          />
        </button>
        <input
          type="tel"
          className="phone-num"
          value={num}
          onChange={(e) => setNum(e.target.value.replace(/[^\d\s-]/g, ""))}
          placeholder="6 12 34 56 78"
          inputMode="tel"
        />
        {open && (
          <ul className="phone-menu">
            {DIAL_CODES.map((d) => (
              <li
                key={d.code}
                className={"phone-item" + (d.code === selected.code ? " on" : "")}
                onClick={() => {
                  setSelected(d);
                  setOpen(false);
                }}
              >
                <img
                  src={`https://flagcdn.com/24x18/${d.code.toLowerCase()}.png`}
                  alt={d.label}
                  width="24"
                  height="18"
                  style={{ borderRadius: 2, flexShrink: 0 }}
                />
                <span className="phone-item-label">{d.label}</span>
                <span className="mono phone-item-dial">{d.dial}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
