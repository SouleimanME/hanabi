/** Menu principal en tiroir, ouvert par le bouton burger de l'en-tete.
 *
 * Reserve aux petits ecrans : sous 640 px, l'en-tete masque la moitie de ses
 * actions (classe .hide-sm) et la barre du bas n'en reprend que quatre. Les
 * categories, la langue, le theme et les pages legales n'etaient alors
 * atteignables qu'en faisant defiler toute la page. Ce panneau les rassemble.
 *
 * Au-dessus de 640 px, la barre d'actions de l'en-tete suffit : le tiroir et
 * son voile sont masques en CSS (voir responsive.css).
 */
import {
  X,
  Home as HomeIcon,
  Heart,
  User,
  Moon,
  Sun,
  Globe,
  Palette,
  Bookmark,
  ReceiptText,
  ContactRound,
} from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { LANGS } from "../../i18n/index.js";
import { CATEGORIES } from "../../lib/constants.js";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";
import { LogoMark } from "../brand/LogoMark.jsx";
import { Dropdown } from "../ui/Dropdown.jsx";

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

  /** Toute navigation referme le panneau : le laisser ouvert masquerait
   *  l'ecran qu'on vient de demander. */
  const go = (action) => () => {
    action();
    onClose();
  };

  return (
    <>
      <div className={"scrim menu-scrim" + (open ? " show" : "")} onClick={onClose} />
      <aside
        ref={ref}
        className={"msheet" + (open ? " open" : "")}
        aria-hidden={!open}
        aria-label={t("menu")}
      >
        <div className="msheet-hd">
          <div className="logo msheet-logo">
            <LogoMark size={26} />
            HANABI<span className="logo-jp">花火</span>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label={t("close")}>
            <X size={18} />
          </button>
        </div>

        <div className="msheet-body">
          <nav className="msheet-nav" aria-label={t("menu")}>
            <button className={view === "home" ? "on" : ""} onClick={go(onGoHome)}>
              <HomeIcon size={18} />
              {t("shop")}
            </button>
            <button className={view === "wishlist" ? "on" : ""} onClick={go(onGoWishlist)}>
              <Heart size={18} fill={wishlistCount ? "currentColor" : "none"} />
              {t("favs")}
              {wishlistCount > 0 && <i className="msheet-count">{wishlistCount}</i>}
            </button>
            <button className={view === "saved" ? "on" : ""} onClick={go(onGoSaved)}>
              <Bookmark size={18} />
              {t("saved")}
              {savedCount > 0 && <i className="msheet-count">{savedCount}</i>}
            </button>
          </nav>

          <section className="msheet-sec">
            <h4>{t("myAccount")}</h4>
            <nav className="msheet-nav" aria-label={t("myAccount")}>
              {/* Hors session, les deux entrees meneraient a un ecran vide :
                  on ne propose alors que la porte d'entree. */}
              {user ? (
                <>
                  <button onClick={go(onGoOrders)}>
                    <ReceiptText size={18} />
                    {t("myOrders")}
                  </button>
                  <button onClick={go(onGoInfo)}>
                    <ContactRound size={18} />
                    {t("myInfo")}
                  </button>
                </>
              ) : (
                <button onClick={go(onGoAccount)}>
                  <User size={18} />
                  {t("signin")}
                </button>
              )}
            </nav>
          </section>

          <section className="msheet-sec">
            <h4>{t("categories")}</h4>
            <div className="msheet-chips">
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  className={"chip" + (category === c ? " on" : "")}
                  onClick={go(() => onGoCategory(c))}
                >
                  {t("cat_" + c)}
                </button>
              ))}
            </div>
          </section>

          <section className="msheet-sec">
            <h4>{t("settings")}</h4>
            <div className="msheet-row">
              <span>
                <Globe size={15} />
                {t("language")}
              </span>
              <Dropdown
                pill
                value={lang}
                onChange={onLangChange}
                options={LANGS.map((l) => ({ value: l.code, label: l.label }))}
              />
            </div>
            <div className="msheet-row">
              <span>
                <Palette size={15} />
                {t("theme")}
              </span>
              {/* Le theme reste visible derriere le panneau : pas de fermeture,
                  pour pouvoir comparer les deux teintes d'un coup d'oeil. */}
              <button className="btn-ghost sm" onClick={onToggleTheme}>
                {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
                {theme === "dark" ? t("themeLight") : t("themeDark")}
              </button>
            </div>
          </section>

          <section className="msheet-sec">
            <h4>{t("information")}</h4>
            <div className="msheet-legal">
              {LEGAL_PAGES.map((page) => (
                <button key={page} onClick={go(() => onOpenLegal(page))}>
                  {t("legal_" + page)}
                </button>
              ))}
            </div>
          </section>
        </div>
      </aside>
    </>
  );
}
