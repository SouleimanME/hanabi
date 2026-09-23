/** Saisie d'une note : cinq boutons radio, navigables aux fleches. */
import { useState } from "react";
import { Star } from "lucide-react";
import { useT } from "../../i18n/context.jsx";

export function StarInput({ value, onChange }) {
  const t = useT();
  const [survol, setSurvol] = useState(0);
  const affiche = survol || value;

  const surTouche = (e) => {
    const pas = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
    if (!pas) return;
    e.preventDefault();
    const suivant = Math.min(5, Math.max(1, value + pas));
    onChange(suivant);
    e.currentTarget.querySelectorAll('[role="radio"]')[suivant - 1]?.focus();
  };

  return (
    <div
      className="star-input"
      role="radiogroup"
      aria-label={t("ratingLabel")}
      onKeyDown={surTouche}
    >
      {[1, 2, 3, 4, 5].map((i) => (
        <button
          key={i}
          type="button"
          role="radio"
          aria-checked={value === i}
          tabIndex={value === i ? 0 : -1}
          aria-label={t("starsN", { n: i })}
          onMouseEnter={() => setSurvol(i)}
          onMouseLeave={() => setSurvol(0)}
          onClick={() => onChange(i)}
        >
          <Star
            size={22}
            strokeWidth={1.5}
            fill={i <= affiche ? "currentColor" : "none"}
            className={i <= affiche ? undefined : "star-empty"}
            aria-hidden="true"
          />
        </button>
      ))}
    </div>
  );
}
