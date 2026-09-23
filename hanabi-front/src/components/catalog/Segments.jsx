/** Filtre exclusif par univers : un groupe de boutons radio. */
import { useRef } from "react";
import { useT } from "../../i18n/context.jsx";

export function Segments({ categories, value, onChange, counts }) {
  const t = useT();
  const groupe = useRef(null);

  const surTouche = (e) => {
    const index = categories.indexOf(value);
    const dernier = categories.length - 1;
    const suivant = {
      ArrowRight: index === dernier ? 0 : index + 1,
      ArrowDown: index === dernier ? 0 : index + 1,
      ArrowLeft: index === 0 ? dernier : index - 1,
      ArrowUp: index === 0 ? dernier : index - 1,
      Home: 0,
      End: dernier,
    }[e.key];
    if (suivant === undefined) return;
    e.preventDefault();
    onChange(categories[suivant]);
    groupe.current?.querySelectorAll('[role="radio"]')[suivant]?.focus();
  };

  return (
    <div
      className="segments"
      role="radiogroup"
      aria-label={t("filterBy")}
      ref={groupe}
      onKeyDown={surTouche}
    >
      {categories.map((c) => (
        <button
          key={c}
          type="button"
          role="radio"
          aria-checked={value === c}
          tabIndex={value === c ? 0 : -1}
          onClick={() => onChange(c)}
        >
          {t("cat_" + c)}
          {counts?.[c] != null && <span className="segment-count">{counts[c]}</span>}
        </button>
      ))}
    </div>
  );
}
