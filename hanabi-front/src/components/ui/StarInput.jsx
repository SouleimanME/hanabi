/** Saisie d'une note en etoiles, avec apercu au survol. */
import { useState } from "react";
import { Star } from "lucide-react";

export function StarInput({ value, onChange }) {
  const [hov, setHov] = useState(0);
  return (
    <span className="star-input">
      {[1, 2, 3, 4, 5].map((i) => (
        <button
          key={i}
          type="button"
          onMouseEnter={() => setHov(i)}
          onMouseLeave={() => setHov(0)}
          onClick={() => onChange(i)}
          aria-label={`${i}`}
        >
          <Star
            size={22}
            strokeWidth={1.5}
            fill={i <= (hov || value) ? "currentColor" : "none"}
            opacity={i <= (hov || value) ? 1 : 0.35}
          />
        </button>
      ))}
    </span>
  );
}
