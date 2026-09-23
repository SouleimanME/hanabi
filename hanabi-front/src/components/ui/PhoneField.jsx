/** Telephone : indicatif en liste native, numero national a cote. */
import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { DIAL_CODES } from "../../lib/dialCodes.js";

export function PhoneField({ onChange, label }) {
  const t = useT();
  const id = useId();
  const [indicatif, setIndicatif] = useState(DIAL_CODES[0].code);
  const [numero, setNumero] = useState("");

  // Le parent recree `onChange` a chaque rendu : on le garde dans une ref pour
  // ne pas relancer l'effet en boucle.
  const notifier = useRef(onChange);
  notifier.current = onChange;

  useEffect(() => {
    const pays = DIAL_CODES.find((d) => d.code === indicatif) ?? DIAL_CODES[0];
    notifier.current(`${pays.dial} ${numero}`);
  }, [indicatif, numero]);

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="phone-row">
        <span className="select">
          <select
            aria-label={t("dialCode")}
            value={indicatif}
            onChange={(e) => setIndicatif(e.target.value)}
          >
            {DIAL_CODES.map((d) => (
              <option key={d.code} value={d.code}>
                {d.code} {d.dial}
              </option>
            ))}
          </select>
          <ChevronDown size={16} aria-hidden="true" />
        </span>
        <input
          id={id}
          type="tel"
          value={numero}
          onChange={(e) => setNumero(e.target.value.replace(/[^\d\s-]/g, ""))}
          placeholder="6 12 34 56 78"
          inputMode="tel"
          autoComplete="tel-national"
        />
      </div>
    </div>
  );
}
