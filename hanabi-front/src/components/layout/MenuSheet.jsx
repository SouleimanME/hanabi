/** Menu des petits ecrans : ce que l'en-tete replie sous 40rem. */
import { X, ChevronDown } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import {
  PictoBoutique,
  PictoCommandes,
  PictoCompte,
  PictoFavori,
  PictoGarde,
  PictoTheme,
} from "../brand/Pictos.jsx";
import { LANGS } from "../../i18n/index.js";
import { CATEGORIES } from "../../lib/constants.js";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";
import { LogoMark } from "../brand/LogoMark.jsx";

const LEGAL_PAGES = ["mentions", "cgv", "confidentialite", "cookies"];

export function MenuSheet({
  open,
  onClose,
  user,
  view,
  lang,
  onLangChange,
  theme,
  onToggleTheme,
  wishlistCount,
  savedCount,
  category,
  onGoCategory,
  onGoHome,
  onGoWishlist,
  onGoSaved,
  onGoAccount,
  onGoOrders,
  onGoInfo,
  onOpenLegal,
}) {
  const t = useT();
  const ref = useFocusTrap(open);

  const go = (action) => () => {
    action();
    onClose();
  };

  return (
    <>
      <div className="scrim" data-open={open} onClick={onClose} aria-hidden="true" />
      <aside
        ref={ref}
        className="sheet sheet-menu"
        data-open={open}
        role="dialog"
        aria-modal="true"
        aria-label={t("menu")}
        inert={open ? undefined : ""}
      >
        <div className="sheet-head">
          <span className="sheet-brand">
            <LogoMark size={26} />
            <span className="brand-word">HANABI</span>
          </span>
          <button className="icon-btn" onClick={onClose} aria-label={t("close")}>
            <X size={20} />
          </button>
        </div>

        <div className="sheet-body menu-body">
          <nav aria-label={t("menu")}>
            <ul className="menu-list">
              <li>
                <button aria-current={view === "home" ? "page" : undefined} onClick={go(onGoHome)}>
                  <PictoBoutique /> {t("shop")}
                </button>
              </li>
              <li>
                <button
                  aria-current={view === "wishlist" ? "page" : undefined}
                  onClick={go(onGoWishlist)}
                >
                  <PictoFavori plein={wishlistCount > 0} /> {t("favs")}
                  {wishlistCount > 0 && <span className="menu-count">{wishlistCount}</span>}
                </button>
              </li>
              <li>
                <button
                  aria-current={view === "saved" ? "page" : undefined}
                  onClick={go(onGoSaved)}
                >
                  <PictoGarde /> {t("saved")}
                  {savedCount > 0 && <span className="menu-count">{savedCount}</span>}
                </button>
              </li>
            </ul>
          </nav>

          <section className="menu-section">
            <h2>{t("myAccount")}</h2>
            <ul className="menu-list">
              {user ? (
                <>
                  <li>
                    <button onClick={go(onGoOrders)}>
                      <PictoCommandes /> {t("myOrders")}
                    </button>
                  </li>
                  <li>
                    <button onClick={go(onGoInfo)}>
                      <PictoCompte /> {t("myInfo")}
                    </button>
                  </li>
                </>
              ) : (
                <li>
                  <button onClick={go(onGoAccount)}>
                    <PictoCompte /> {t("signin")}
                  </button>
                </li>
              )}
            </ul>
          </section>

          <section className="menu-section">
            <h2>{t("categories")}</h2>
            <ul className="menu-chips">
              {CATEGORIES.map((c) => (
                <li key={c}>
                  <button
                    className="chip"
                    aria-pressed={category === c}
                    onClick={go(() => onGoCategory(c))}
                  >
                    {t("cat_" + c)}
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="menu-section">
            <h2>{t("settings")}</h2>
            <div className="menu-row">
              <label htmlFor="menu-langue">{t("language")}</label>
              <span className="select">
                <select
                  id="menu-langue"
                  value={lang}
                  onChange={(e) => onLangChange(e.target.value)}
                >
                  {LANGS.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={16} aria-hidden="true" />
              </span>
            </div>
            <div className="menu-row">
              <span>{t("theme")}</span>
              <button className="btn btn-quiet" onClick={onToggleTheme}>
                <PictoTheme
                  taille={18}
                  className={theme === "dark" ? "picto-theme is-dark" : "picto-theme"}
                />
                {theme === "dark" ? t("themeLight") : t("themeDark")}
              </button>
            </div>
          </section>

          <section className="menu-section">
            <h2>{t("information")}</h2>
            <ul className="menu-list menu-legal">
              {LEGAL_PAGES.map((page) => (
                <li key={page}>
                  <button onClick={go(() => onOpenLegal(page))}>{t("legal_" + page)}</button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </aside>
    </>
  );
}
