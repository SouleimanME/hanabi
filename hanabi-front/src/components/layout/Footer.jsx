/** Pied de page : identite, raccourcis catalogue et acces aux pages legales. */
import { useT } from "../../i18n/context.jsx";
import { LogoMark } from "../brand/LogoMark.jsx";
import { FujiScene, SeigaihaBand } from "../brand/Ornaments.jsx";

const LEGAL_PAGES = ["mentions", "cgv", "confidentialite", "cookies"];
const SHOP_CATEGORIES = ["Compagnons", "Tradition", "Collection"];

export function Footer({ onGoCategory, onOpenLegal }) {
  const t = useT();

  return (
    <footer className="ft">
      {/* Frise de vagues en cretes : marque la bascule vers le pied de page. */}
      <div className="ft-crest">
        <SeigaihaBand height={34} />
      </div>
      <FujiScene />
      <div className="ft-in">
        <div>
          <div className="logo ft-logo">
            <LogoMark size={30} />
            HANABI<span className="logo-jp">花火</span>
          </div>
          <p className="ft-tag">{t("ftTag")}</p>
        </div>

        <div className="ft-cols">
          <div>
            <h4>{t("shop")}</h4>
            {SHOP_CATEGORIES.map((c) => (
              <button key={c} className="ft-link" onClick={() => onGoCategory(c)}>
                {t("cat_" + c)}
              </button>
            ))}
          </div>
          <div>
            <h4>{t("help")}</h4>
            <span>{t("lLivraison")}</span>
            <span>{t("lRetours")}</span>
            <span>{t("lDropTrack")}</span>
            <span>{t("lContact")}</span>
          </div>
          <div>
            <h4>{t("maisonCol")}</h4>
            <span>{t("lStory")}</span>
            <span>{t("lAteliers")}</span>
            <span>{t("lJournal")}</span>
          </div>
        </div>
      </div>

      <div className="ft-legal">
        <div className="ft-legal-in">
          <span>© {new Date().getFullYear()} Hanabi</span>
          <div className="ft-legal-links">
            {LEGAL_PAGES.map((page) => (
              <button key={page} className="ft-legal-link" onClick={() => onOpenLegal(page)}>
                {t("legal_" + page)}
              </button>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
