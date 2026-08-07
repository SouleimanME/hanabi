/** En-tete fixe : identite, actions globales et filtres du catalogue.
 *
 * L'en-tete se retracte au defilement vers le bas et reapparait au defilement
 * vers le haut (voir `useHideOnScroll`), pour rendre de la hauteur utile sur
 * mobile sans priver l'utilisateur du panier.
 */
import { forwardRef } from "react";
import { ShoppingBag, User, Search, Heart, Moon, Sun, Globe, Menu } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { LANGS } from "../../i18n/index.js";
import { CATEGORIES } from "../../lib/constants.js";
import { Dropdown } from "../ui/Dropdown.jsx";
import { LogoMark } from "../brand/LogoMark.jsx";
import { ScrollProgress } from "./ScrollProgress.jsx";

// L'etat de defilement - en-tete retracte ou non - n'est plus une prop : il
// est pose directement sur ce noeud par `useHideOnScroll`, via la ref
// transmise. Faire transiter cet etat par React re-rendait toute l'application
// a chaque changement de sens du defilement. La classe `.hidden` est donc
// absente du rendu initial et posee a la main.
export const Header = forwardRef(function Header(
  {
    lang,
    onLangChange,
    theme,
    onToggleTheme,
    user,
    cartCount,
    wishlistCount,
    showFilters,
    query,
    onQueryChange,
    category,
    onCategoryChange,
    onGoHome,
    onGoWishlist,
    onGoAccount,
    onOpenAuth,
    onOpenCart,
    onOpenMenu,
  },
  ref,
) {
  const t = useT();

  return (
    <header className="hd" ref={ref}>
      <div className="hd-in">
        {/* Le logo ramene a l'accueil, comme partout ailleurs sur le web.
            `aria-label` explicite la destination : lu seul, « HANABI 花火 »
            ne dit pas qu'il s'agit d'un lien. */}
        <button
          className="logo"
          onClick={onGoHome}
          aria-label={t("ariaHome")}
          title={t("ariaHome")}
        >
          <LogoMark size={34} />
          HANABI<span className="logo-jp">花火</span>
        </button>

        <div className="hd-r">
          {/* Le selecteur de langue prend la largeur d'un nom de langue entier :
              sous 640 px il ne laissait plus de place au reste. Il vit alors
              dans le menu burger, avec les categories et le theme. */}
          <div className="hide-sm">
            <Dropdown
              pill
              value={lang}
              onChange={onLangChange}
              icon={<Globe size={14} />}
              options={LANGS.map((l) => ({ value: l.code, label: l.label }))}
            />
          </div>

          <button className="icon-btn" onClick={onToggleTheme} aria-label={t("ariaTheme")}>
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          <button
            className="icon-btn hide-sm"
            onClick={onGoWishlist}
            aria-label={t("ariaFavorites")}
          >
            <Heart size={18} fill={wishlistCount ? "currentColor" : "none"} />
            {wishlistCount > 0 && <span className="badge alt">{wishlistCount}</span>}
          </button>

          {user ? (
            <button className="icon-btn account hide-sm" onClick={onGoAccount}>
              <span className="account-name">{user.name.split(" ")[0]}</span>
              <User size={16} />
            </button>
          ) : (
            <button className="icon-btn hide-sm" onClick={onOpenAuth} aria-label={t("ariaAccount")}>
              <User size={18} />
            </button>
          )}

          {/* `hide-sm`, comme les favoris et le compte : sous 640 px, ces trois
              actions vivent dans la barre du bas (MobileNav), qui affiche aussi
              le compteur. Garde dans l'en-tete, le panier faisait doublon et,
              faute de place, debordait de l'ecran : on n'en voyait qu'un bout
              coince dans l'angle. */}
          <button className="icon-btn cart-btn hide-sm" onClick={onOpenCart} aria-label={t("cart")}>
            <ShoppingBag size={18} />
            {cartCount > 0 && (
              <span className="badge" key={cartCount}>
                {cartCount}
              </span>
            )}
          </button>

          {/* Miroir du `hide-sm` : le burger n'existe que la ou l'en-tete se
              vide de ses actions. */}
          <button
            className="icon-btn only-sm"
            onClick={onOpenMenu}
            aria-label={t("menu")}
            aria-haspopup="dialog"
          >
            <Menu size={20} />
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="catbar">
          <div className="catbar-in">
            <div className="search">
              <Search size={16} />
              <input
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                placeholder={t("search")}
                aria-label={t("search")}
              />
            </div>
            <div className="chips">
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  className={"chip" + (category === c ? " on" : "")}
                  onClick={() => onCategoryChange(c)}
                >
                  {t("cat_" + c)}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      <ScrollProgress />
    </header>
  );
});
