/** Pages legales en fenetre. Les textes non traduits retombent sur le
 *  francais, qui fait foi. */
import { X } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { LEGAL_CONTENT, LEGAL_UPDATED } from "../../content/legal.js";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";

/** Mini-format maison : titres entre ** et puces. Un moteur Markdown serait
 *  une dependance pour deux regles. */
function rendreTexte(text) {
  const blocs = [];
  let puces = [];
  const viderPuces = (cle) => {
    if (puces.length) {
      blocs.push(
        <ul key={`l${cle}`} className="bullets">
          {puces}
        </ul>,
      );
      puces = [];
    }
  };
  text.split("\n").forEach((ligne, i) => {
    if (ligne.startsWith("•")) {
      puces.push(<li key={i}>{ligne.replace(/^•\s*/, "")}</li>);
      return;
    }
    viderPuces(i);
    if (ligne.startsWith("**") && ligne.endsWith("**")) {
      blocs.push(<h3 key={i}>{ligne.slice(2, -2)}</h3>);
    } else if (ligne.trim()) {
      blocs.push(<p key={i}>{ligne}</p>);
    }
  });
  viderPuces("fin");
  return blocs;
}

export function LegalModal({ page, lang, onClose }) {
  const t = useT();
  const trapRef = useFocusTrap();
  const content = LEGAL_CONTENT[page];
  const localized = content[lang] ?? content.fr;

  return (
    <div className="modal-layer">
      <div className="scrim" data-open="true" onClick={onClose} aria-hidden="true" />
      <div
        ref={trapRef}
        className="modal modal-wide"
        role="dialog"
        aria-modal="true"
        aria-labelledby="legal-titre"
      >
        <div className="sheet-head">
          <h2 id="legal-titre">{localized.title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label={t("close")}>
            <X size={20} />
          </button>
        </div>
        <div className="modal-body legal">
          <p className="notice">{t("legalDraft")}</p>
          {rendreTexte(localized.body)}
          <p className="muted">{t("legalUpdated", { date: LEGAL_UPDATED })}</p>
        </div>
      </div>
    </div>
  );
}
