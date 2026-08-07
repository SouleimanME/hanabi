/** Affichage des pages legales en modale. */
import { X, Info } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { LEGAL_CONTENT, LEGAL_UPDATED } from "../../content/legal.js";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";

const FALLBACK_LANG = "fr";

/**
 * Transforme le texte legal en elements React.
 *
 * Mini-format maison plutot qu'un moteur Markdown complet : le besoin se
 * limite a des titres et des puces, et cela evite une dependance de plus.
 */
function renderLegal(text) {
  return text.split("\n").map((line, i) => {
    if (line.startsWith("**") && line.endsWith("**")) {
      return (
        <h3 key={i} className="legal-h3">
          {line.slice(2, -2)}
        </h3>
      );
    }
    if (line.startsWith("•")) {
      return (
        <p key={i} className="legal-bullet">
          {line}
        </p>
      );
    }
    if (line.trim() === "") return <div key={i} className="legal-gap" />;
    return (
      <p key={i} className="legal-p">
        {line}
      </p>
    );
  });
}

export function LegalModal({ page, lang, onClose }) {
  const t = useT();
  const trapRef = useFocusTrap();
  const content = LEGAL_CONTENT[page];
  // Toutes les pages ne sont pas traduites dans toutes les langues :
  // on retombe sur le francais, qui fait foi juridiquement.
  const localized = content[lang] ?? content[FALLBACK_LANG];

  return (
    <div className="modal-scrim" onClick={onClose}>
      <div
        ref={trapRef}
        className="modal legal-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={localized.title}
      >
        <button className="icon-btn modal-x" onClick={onClose} aria-label={t("close")}>
          <X size={18} />
        </button>
        <h2 className="modal-h">{localized.title}</h2>
        {/* Les textes contiennent des champs a renseigner par l'exploitant.
            Le signaler explicitement evite de laisser croire que la boutique
            est juridiquement prete a encaisser de vraies commandes. */}
        <div className="legal-notice">
          <Info size={15} />
          <span>{t("legalDraft")}</span>
        </div>
        <div className="legal-body">{renderLegal(localized.body)}</div>
        <p className="legal-updated mono small muted">
          {t("legalUpdated", { date: LEGAL_UPDATED })}
        </p>
      </div>
    </div>
  );
}
