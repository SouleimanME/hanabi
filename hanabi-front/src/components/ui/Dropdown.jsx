/** Menu deroulant accessible, en remplacement de <select>.
 *
 * Les <select> natifs ne sont pas stylables de maniere fiable entre
 * navigateurs. On reimplemente donc le motif listbox de l'ARIA APG, avec
 * fermeture au clic exterieur.
 */
import { useState, useEffect, useRef } from "react";
import { Check, ChevronDown } from "lucide-react";

export function Dropdown({ value, onChange, options, icon, pill }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const current = options.find((o) => o.value === value);
  useEffect(() => {
    const fn = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);
  return (
    <div className={"dd" + (pill ? " dd-pill" : "")} ref={ref}>
      <button
        className="dd-trigger"
        onClick={() => setOpen((s) => !s)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {icon && <span className="dd-icon">{icon}</span>}
        <span className="dd-label">{current?.label}</span>
        <ChevronDown size={13} className={"dd-chevron" + (open ? " open" : "")} />
      </button>
      {open && (
        <ul className="dd-menu" role="listbox">
          {options.map((o) => (
            <li
              key={o.value}
              role="option"
              aria-selected={o.value === value}
              className={"dd-item" + (o.value === value ? " on" : "")}
              onClick={() => {
                onChange(o.value);
                setOpen(false);
              }}
            >
              {o.value === value && <Check size={12} strokeWidth={3} />}
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
