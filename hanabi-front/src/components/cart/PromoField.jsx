/** Saisie et affichage d'un code promo.
 *
 * La validation est faite par le serveur : `onApply` renvoie un message
 * d'erreur, ou `null` si le code est accepte.
 */
import { useState } from "react";
import { Tag } from "lucide-react";
import { useT } from "../../i18n/context.jsx";

export function PromoField({ promo, promoLabel, onApply, onClear }) {
  const t = useT();
  const [code, setCode] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const apply = async () => {
    setBusy(true);
    const m = await onApply(code);
    setBusy(false);
    setErr(m);
    if (!m) setCode("");
  };
  if (promo)
    return (
      <div className="promo-on">
        <span>
          <Tag size={14} /> <strong>{promo}</strong> · {promoLabel}
        </span>
        <button className="link-del" onClick={onClear}>
          {t("removeC")}
        </button>
      </div>
    );
  return (
    <div className="promo">
      <div className="promo-row">
        <input
          value={code}
          onChange={(e) => {
            setCode(e.target.value);
            setErr(null);
          }}
          placeholder={t("promoPh")}
          aria-label="Promo"
          onKeyDown={(e) => e.key === "Enter" && apply()}
        />
        <button className="btn-ghost sm" onClick={apply} disabled={busy}>
          {t("apply")}
        </button>
      </div>
      {err && <span className="promo-err">{err}</span>}
      <span className="promo-hint mono small">{t("promoHint")}</span>
    </div>
  );
}
