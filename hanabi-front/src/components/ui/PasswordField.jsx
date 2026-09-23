/** Champ mot de passe, jauge et liste des regles. */
import { useId, useState } from "react";
import { Check, Eye, EyeOff } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { PW_RULES, pwScore } from "../../lib/password.js";

export function PwField({
  label,
  value,
  onChange,
  onKeyDown,
  placeholder,
  // Decide si un gestionnaire de mots de passe propose de remplir ou de generer
  autoComplete = "current-password",
  name,
  invalid = false,
}) {
  const t = useT();
  const id = useId();
  const [visible, setVisible] = useState(false);
  const [majuscules, setMajuscules] = useState(false);

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="pw-row">
        <input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          onChange={onChange}
          onKeyDown={(e) => {
            // Verrouillage majuscules : premiere cause d'echec de connexion
            // inexplique, puisque la saisie est masquee.
            if (e.getModifierState) setMajuscules(e.getModifierState("CapsLock"));
            onKeyDown?.(e);
          }}
          placeholder={placeholder}
          autoComplete={autoComplete}
          name={name}
          aria-invalid={invalid || undefined}
          aria-describedby={majuscules ? `${id}-caps` : undefined}
          spellCheck="false"
        />
        <button
          type="button"
          className="pw-toggle"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? t("pwHide") : t("pwShow")}
          aria-pressed={visible}
        >
          {visible ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      {majuscules && (
        <span className="field-hint" id={`${id}-caps`} role="status">
          {t("capsLock")}
        </span>
      )}
    </div>
  );
}

const PALIERS = ["pwWeak", "pwFair", "pwGood", "pwStrong"];

export function PwStrength({ value }) {
  const t = useT();
  if (!value) return null;

  // Le palier suit la proportion de regles satisfaites, pas leur nombre
  const ratio = pwScore(value) / PW_RULES.length;
  const palier = Math.min(PALIERS.length - 1, Math.max(0, Math.ceil(ratio * PALIERS.length) - 1));

  return (
    <div className="pw-strength" data-level={palier}>
      <div className="pw-bars" aria-hidden="true">
        {PALIERS.map((cle, i) => (
          <span key={cle} className={i <= palier ? "on" : undefined} />
        ))}
      </div>
      <span className="pw-level">{t(PALIERS[palier])}</span>
    </div>
  );
}

export function PwChecklist({ value }) {
  const t = useT();
  if (!value) return null;
  return (
    <ul className="pw-rules">
      {PW_RULES.map((r) => {
        const ok = r.test(value);
        return (
          <li key={r.key} data-ok={ok}>
            <span className="pw-rule-mark" aria-hidden="true">
              {ok ? <Check size={12} strokeWidth={3} /> : null}
            </span>
            {r.label(t)}
            <span className="sr-only">{ok ? t("pwRuleOk") : t("pwRuleMissing")}</span>
          </li>
        );
      })}
    </ul>
  );
}
