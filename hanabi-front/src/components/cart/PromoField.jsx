/** Code promo. Le serveur valide : `onApply` rend un message d'erreur, ou
 *  `null` si le code est accepte. */
import { useId, useState } from "react";
import { Tag } from "lucide-react";
import { useT } from "../../i18n/context.jsx";

// Les codes de la démonstration (hanabi-back/app/seed.py), et ce qu'ils offrent
const CODES_DU_MOMENT = [
  { code: "BIENVENUE10", key: "promoBienvenue" },
  { code: "DROP5", key: "promoDrop" },
  { code: "PORTOFFERT", key: "promoPort" },
];

export function PromoField({ promo, promoLabel, onApply, onClear }) {
  const t = useT();
  const id = useId();
  const [code, setCode] = useState("");
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  const essayer = async (valeur) => {
    setEnvoi(true);
    const message = await onApply(valeur);
    setEnvoi(false);
    setErreur(message);
    if (!message) setCode("");
  };

  const appliquer = (e) => {
    e.preventDefault();
    essayer(code);
  };

  if (promo) {
    return (
      <div className="promo-on">
        <span>
          <Tag size={16} aria-hidden="true" /> <span className="code">{promo}</span>
          {promoLabel ? ` · ${promoLabel}` : ""}
        </span>
        <button className="link" onClick={onClear}>
          {t("removeC")}
        </button>
      </div>
    );
  }

  return (
    <form className="promo" onSubmit={appliquer}>
      <label htmlFor={id}>{t("promoPh")}</label>
      <div className="promo-row">
        <input
          id={id}
          value={code}
          onChange={(e) => {
            setCode(e.target.value);
            setErreur(null);
          }}
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck="false"
          aria-invalid={erreur ? true : undefined}
          aria-describedby={erreur ? `${id}-err` : undefined}
        />
        <button className="btn btn-quiet" type="submit" disabled={envoi || !code.trim()}>
          {t("apply")}
        </button>
      </div>
      {erreur && (
        <p className="field-error" id={`${id}-err`} role="alert">
          {erreur}
        </p>
      )}
      {/* Un code se tape rarement de mémoire : un clic l'applique */}
      <div className="promo-codes" role="group" aria-labelledby={`${id}-codes`}>
        <span className="promo-codes-titre" id={`${id}-codes`}>
          {t("promoTry")}
        </span>
        {CODES_DU_MOMENT.map(({ code: valeur, key }) => (
          <button
            key={valeur}
            type="button"
            className="promo-code"
            disabled={envoi}
            onClick={() => essayer(valeur)}
          >
            <span className="code">{valeur}</span>
            <span>{t(key)}</span>
          </button>
        ))}
      </div>
    </form>
  );
}
