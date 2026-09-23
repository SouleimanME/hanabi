/** Préférences de confidentialité, rouvrables depuis le pied de page. */
import { useId, useState } from "react";
import { X } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";

export function PreferencesCookies({ choix, onEnregistrer, onClose, onEnSavoirPlus }) {
  const t = useT();
  const trapRef = useFocusTrap();
  const idAudience = useId();
  // Rien n'est coché d'avance : un accord se donne, il ne se présume pas
  const [audience, setAudience] = useState(choix?.audience === true);

  return (
    <div className="modal-layer">
      <div className="scrim" data-open="true" onClick={onClose} aria-hidden="true" />
      <div
        ref={trapRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="prefs-titre"
      >
        <div className="sheet-head">
          <h2 id="prefs-titre">{t("consentPrefsTitle")}</h2>
          <button className="icon-btn" onClick={onClose} aria-label={t("close")}>
            <X size={20} />
          </button>
        </div>
        <div className="modal-body consent-prefs">
          <section className="consent-finalite">
            <div className="consent-finalite-tete">
              <h3>{t("consentNeeded")}</h3>
              <span className="consent-toujours">{t("consentAlways")}</span>
            </div>
            <p>{t("consentNeededText")}</p>
          </section>

          <section className="consent-finalite">
            <div className="consent-finalite-tete">
              <h3 id={`${idAudience}-titre`}>{t("consentAudience")}</h3>
              <input
                type="checkbox"
                role="switch"
                className="interrupteur"
                checked={audience}
                onChange={(e) => setAudience(e.target.checked)}
                aria-labelledby={`${idAudience}-titre`}
                aria-describedby={`${idAudience}-texte`}
              />
            </div>
            <p id={`${idAudience}-texte`}>{t("consentAudienceText")}</p>
          </section>

          <button type="button" className="link" onClick={onEnSavoirPlus}>
            {t("consentMore")}
          </button>
        </div>
        <div className="consent-prefs-pied">
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => onEnregistrer({ audience: false })}
          >
            {t("consentRefuse")}
          </button>
          <button
            type="button"
            className="btn btn-quiet"
            onClick={() => onEnregistrer({ audience: true })}
          >
            {t("consentAccept")}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => onEnregistrer({ audience })}
          >
            {t("consentSave")}
          </button>
        </div>
      </div>
    </div>
  );
}
