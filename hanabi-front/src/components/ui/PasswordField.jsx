/** Champ mot de passe et ses indicateurs de robustesse.
 *
 * Les regles sont affichees en direct : l'utilisateur voit ce qui manque au
 * lieu de decouvrir un refus a la validation. Les regles elles-memes vivent
 * dans `lib/password.js`, car le formulaire d'inscription s'en sert aussi
 * pour bloquer l'envoi.
 */
import { useState } from "react";
import { Check } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { PW_RULES, pwScore } from "../../lib/password.js";

export function PwField({
  label,
  value,
  onChange,
  onKeyDown,
  placeholder,
  // "current-password" a la connexion, "new-password" a l'inscription : c'est ce
  // qui decide si un gestionnaire de mots de passe propose de remplir ou de
  // generer. Sans cet attribut, il devine - souvent mal.
  autoComplete = "current-password",
  name,
  invalid = false,
}) {
  const [show, setShow] = useState(false);
  const [caps, setCaps] = useState(false);
  const t = useT();

  return (
    <label className="field">
      <span>{label}</span>
      <div className="pw-wrap">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={onChange}
          onKeyDown={(e) => {
            // Verrouillage majuscules : premiere cause d'echec de connexion
            // inexpliquee, puisque le champ masque ce qui est saisi.
            if (e.getModifierState) setCaps(e.getModifierState("CapsLock"));
            onKeyDown?.(e);
          }}
          placeholder={placeholder || "••••••••"}
          autoComplete={autoComplete}
          name={name}
          aria-invalid={invalid || undefined}
          spellCheck="false"
        />
        <button
          type="button"
          className="pw-eye"
          onClick={() => setShow((s) => !s)}
          aria-label={show ? "Cacher" : "Voir"}
          tabIndex={-1}
        >
          {show ? (
            <svg
              width="17"
              height="17"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
              <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
              <line x1="1" y1="1" x2="23" y2="23" />
            </svg>
          ) : (
            <svg
              width="17"
              height="17"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          )}
        </button>
      </div>
      {caps && (
        <span className="pw-caps" role="status">
          {t("capsLock")}
        </span>
      )}
    </label>
  );
}

const STRENGTH_TIERS = [
  { key: "pwWeak", color: "#E05252" },
  { key: "pwFair", color: "#D9742E" },
  { key: "pwGood", color: "#C88A1E" },
  { key: "pwStrong", color: "#3E7A5B" },
];

export function PwStrength({ value }) {
  const t = useT();
  if (!value) return null;

  // Le palier est deduit de la PROPORTION de regles satisfaites, jamais de leur
  // nombre : indexer un tableau de quatre libelles par un score qui peut monter
  // a cinq donnait un libelle vide des que toutes les regles passaient.
  const ratio = pwScore(value) / PW_RULES.length;
  const tierIndex = Math.min(
    STRENGTH_TIERS.length - 1,
    Math.max(0, Math.ceil(ratio * STRENGTH_TIERS.length) - 1),
  );
  const tier = STRENGTH_TIERS[tierIndex];

  return (
    <div className="pw-strength">
      <div className="pw-bars">
        {STRENGTH_TIERS.map((_, i) => (
          <div
            key={i}
            className="pw-bar"
            style={{ background: i <= tierIndex ? tier.color : "var(--line2)" }}
          />
        ))}
      </div>
      <span className="pw-label" style={{ color: tier.color }}>
        {t(tier.key)}
      </span>
    </div>
  );
}

export function PwChecklist({ value }) {
  const t = useT();
  if (!value) return null;
  return (
    <ul className="pw-checklist">
      {PW_RULES.map((r) => (
        <li key={r.key} className={r.test(value) ? "ok" : ""}>
          <span className="pw-check-icon">
            {r.test(value) ? <Check size={11} strokeWidth={3} /> : <span className="pw-dot" />}
          </span>
          {r.label(t)}
        </li>
      ))}
    </ul>
  );
}
