/** Barre de navigation fixe en bas d'ecran, affichee sous 640 px.
 *
 * Reprend les actions que l'en-tete masque sur petit ecran (classe .hide-sm),
 * pour garder favoris, panier et compte a portee de pouce.
 */
import { ShoppingBag, User, Heart, Home as HomeIcon } from "lucide-react";
import { useT } from "../../i18n/context.jsx";

export function MobileNav({
  view,
  cartCount,
  wishlistCount,
  onGoHome,
  onGoWishlist,
  onOpenCart,
  onGoAccount,
}) {
  const t = useT();

  return (
    <nav className="mnav" aria-label={t("ariaNav")}>
      <button className={view === "home" ? "on" : ""} onClick={onGoHome}>
        <HomeIcon size={20} />
        <span>{t("shop")}</span>
      </button>

      <button className={view === "wishlist" ? "on" : ""} onClick={onGoWishlist}>
        <span className="mnav-ic">
          <Heart size={20} fill={wishlistCount ? "currentColor" : "none"} />
          {wishlistCount > 0 && <i>{wishlistCount}</i>}
        </span>
        <span>{t("favs")}</span>
      </button>

      <button onClick={onOpenCart}>
        <span className="mnav-ic">
          <ShoppingBag size={20} />
          {cartCount > 0 && <i>{cartCount}</i>}
        </span>
        <span>{t("cart")}</span>
      </button>

      <button className={view === "account" ? "on" : ""} onClick={onGoAccount}>
        <User size={20} />
        <span>{t("maisonCol")}</span>
      </button>
    </nav>
  );
}
