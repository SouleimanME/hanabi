/** Note en etoiles, en lecture seule. */
import { memo } from "react";
import { Star } from "lucide-react";

export const Stars = memo(function Stars({ value, count, size = 14 }) {
  return (
    <span className="stars" title={`${(value || 0).toFixed(1)} / 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          size={size}
          strokeWidth={1.5}
          fill={i <= Math.round(value || 0) ? "currentColor" : "none"}
          opacity={i <= Math.round(value || 0) ? 1 : 0.35}
        />
      ))}
      {count != null && <span className="stars-c mono">{count > 0 ? `(${count})` : "-"}</span>}
    </span>
  );
});
