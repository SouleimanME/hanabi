/** Pied de page : la tranche de la laque, identique dans les deux themes. */
import { useT } from "../../i18n/context.jsx";
import { LogoMark } from "../brand/LogoMark.jsx";
import { Newsletter } from "./Newsletter.jsx";

const LEGAL_PAGES = ["mentions", "cgv", "confidentialite", "cookies"];
const SHOP_CATEGORIES = ["Figurines", "Décoration", "Luminaires"];

export function Footer({ lang, onGoCategory, onOpenLegal }) {
  const t = useT();

  return (
    <footer className="ft">
      <div className="wrap ft-grid">
        <div className="ft-brand">
          <span className="ft-mark">
            <LogoMark size={28} />
            <span className="brand-word">
              HANABI<span className="jp">花火</span>
            </span>
          </span>
          <p>{t("ftTag")}</p>
        </div>

        <nav className="ft-col" aria-label={t("shop")}>
          <h2>{t("shop")}</h2>
          <ul>
            {SHOP_CATEGORIES.map((c) => (
              <li key={c}>
                <button className="ft-link" onClick={() => onGoCategory(c)}>
                  {t("cat_" + c)}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <nav className="ft-col" aria-label={t("information")}>
          <h2>{t("information")}</h2>
          <ul>
            {LEGAL_PAGES.map((page) => (
              <li key={page}>
                <button className="ft-link" onClick={() => onOpenLegal(page)}>
                  {t("legal_" + page)}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <Newsletter lang={lang} />
      </div>

      <div className="wrap ft-base">
        <span>© {new Date().getFullYear()} Hanabi</span>
        <span>{t("ftFiction")}</span>
      </div>
    </footer>
  );
}
