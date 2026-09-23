/** Note en etoiles, en lecture seule. La valeur est donnee en texte a cote :
 *  les etoiles seules ne se lisent pas au lecteur d'ecran. */
import { memo } from "react";
import { Star } from "lucide-react";

export const Stars = memo(function Stars({ value, size = 14, label }) {
  const plein = Math.round(value || 0);
  return (
    <span className="stars" role="img" aria-label={label ?? `${(value || 0).toFixed(1)} / 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          size={size}
          strokeWidth={1.5}
          fill={i <= plein ? "currentColor" : "none"}
          className={i <= plein ? undefined : "star-empty"}
          aria-hidden="true"
        />
      ))}
    </span>
  );
});
