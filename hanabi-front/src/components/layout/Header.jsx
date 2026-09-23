/** En-tete collant : marque, recherche du catalogue, actions globales. */
import { useEffect, useRef } from "react";

import { useT } from "../../i18n/context.jsx";
import { LANGS } from "../../i18n/index.js";
import { LogoMark } from "../brand/LogoMark.jsx";
import {
  PictoCompte,
  PictoFavori,
  PictoLoupe,
  PictoMenu,
  PictoPanier,
  PictoTheme,
} from "../brand/Pictos.jsx";

export function Header({
  lang,
  onLangChange,
  theme,
  onToggleTheme,
  user,
  cartCount,
  wishlistCount,
  showSearch,
  query,
  onQueryChange,
  onGoHome,
  onGoWishlist,
  onGoAccount,
  onOpenAuth,
  onOpenCart,
  onOpenMenu,
}) {
  const t = useT();
  const champ = useRef(null);

  useEffect(() => {
    if (!showSearch) return undefined;
    const surTouche = (e) => {
      const cible = e.target;
      const enSaisie =
        cible instanceof HTMLElement &&
        (cible.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(cible.tagName));
      if (e.key === "/" && !enSaisie && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        champ.current?.focus();
      }
    };
    window.addEventListener("keydown", surTouche);
    return () => window.removeEventListener("keydown", surTouche);
  }, [showSearch]);

  return (
    <header className="hd">
      <div className="wrap hd-row">
        <button className="brand" onClick={onGoHome} aria-label={t("ariaHome")}>
          <LogoMark size={34} className="brand-mark" />
          <span className="brand-word" aria-hidden="true">
            HANABI<span className="jp">花火</span>
          </span>
        </button>

        {showSearch && (
          <form className="search" role="search" onSubmit={(e) => e.preventDefault()}>
            <label className="sr-only" htmlFor="recherche">
              {t("search")}
            </label>
            <PictoLoupe taille={18} />
            <input
              ref={champ}
              id="recherche"
              type="search"
              value={query}
              onChange={(e) => onQueryChange(e.target.value)}
              placeholder={t("search")}
              autoComplete="off"
              spellCheck="false"
              aria-keyshortcuts="/"
            />
          </form>
        )}

        <div className="hd-actions">
          <label className="lang hide-sm">
            <span className="sr-only">{t("language")}</span>
            <select value={lang} onChange={(e) => onLangChange(e.target.value)}>
              {LANGS.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>

          <button
            className="icon-btn"
            onClick={onToggleTheme}
            aria-label={theme === "dark" ? t("themeToLight") : t("themeToDark")}
          >
            <PictoTheme className={theme === "dark" ? "picto-theme is-dark" : "picto-theme"} />
          </button>

          <button className="icon-btn hide-sm" onClick={onGoWishlist} aria-label={t("favs")}>
            <PictoFavori plein={wishlistCount > 0} />
            {wishlistCount > 0 && <span className="count-badge">{wishlistCount}</span>}
          </button>

          <button
            className="icon-btn hide-sm"
            onClick={user ? onGoAccount : onOpenAuth}
            aria-label={user ? t("myAccount") : t("signin")}
          >
            <PictoCompte />
          </button>

          <button
            className="icon-btn"
            onClick={onOpenCart}
            aria-label={t("cartOpen", { n: cartCount })}
            aria-haspopup="dialog"
          >
            <PictoPanier />
            {cartCount > 0 && <span className="count-badge">{cartCount}</span>}
          </button>

          <button
            className="icon-btn only-sm"
            onClick={onOpenMenu}
            aria-label={t("menu")}
            aria-haspopup="dialog"
          >
            <PictoMenu taille={22} />
          </button>
        </div>
      </div>
    </header>
  );
}
