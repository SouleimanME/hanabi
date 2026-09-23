/** Code promo. Le serveur valide : `onApply` rend un message d'erreur, ou
 *  `null` si le code est accepte. */
import { useId, useState } from "react";
import { Tag } from "lucide-react";
import { useT } from "../../i18n/context.jsx";

export function PromoField({ promo, promoLabel, onApply, onClear }) {
  const t = useT();
  const id = useId();
  const [code, setCode] = useState("");
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  const appliquer = async (e) => {
    e.preventDefault();
    setEnvoi(true);
    const message = await onApply(code);
    setEnvoi(false);
    setErreur(message);
    if (!message) setCode("");
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
          aria-describedby={`${id}-aide`}
        />
        <button className="btn btn-quiet" type="submit" disabled={envoi || !code.trim()}>
          {t("apply")}
        </button>
      </div>
      <p
        className={erreur ? "field-error" : "field-hint"}
        id={`${id}-aide`}
        role={erreur ? "alert" : undefined}
      >
        {erreur || t("promoHint")}
      </p>
    </form>
  );
}
