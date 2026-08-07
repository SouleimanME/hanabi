/** Panier lateral coulissant. */
import { X, ShoppingBag, Trash2, Minus, Plus, ArrowRight, Bookmark } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { ProductArt } from "../brand/ProductArt.jsx";
import { DeliveryNote } from "../ui/DeliveryNote.jsx";
import { PromoField } from "./PromoField.jsx";
import { ShippingGauge } from "./ShippingGauge.jsx";

export function CartDrawer({
  open,
  onClose,
  lines,
  disp,
  onQty,
  onRemove,
  onCheckout,
  promo,
  promoLabel,
  onApplyPromo,
  onClearPromo,
  savedCount,
  onSaveForLater,
  onGoSaved,
  lang,
  eur,
}) {
  const t = useT();
  return (
    <>
      <div className={"scrim" + (open ? " show" : "")} onClick={onClose} />
      <aside className={"drawer" + (open ? " open" : "")} aria-hidden={!open} aria-label="Panier">
        <div className="drawer-hd">
          <h3>
            {t("cart")}{" "}
            {lines.length > 0 && <span className="mono small muted">({lines.length})</span>}
          </h3>
          <button className="icon-btn" onClick={onClose} aria-label="Fermer">
            <X size={18} />
          </button>
        </div>
        {/* Raccourci vers les articles mis de cote. Place au-dessus des lignes
            et non dans le pied du panier : quand on enregistre le dernier
            article, le panier passe a l'ecran vide - un lien loge dans le pied
            disparaitrait juste au moment ou il devient utile. */}
        {savedCount > 0 && (
          <button className="cart-saved" onClick={onGoSaved}>
            <Bookmark size={15} /> {t("saved")}
            <span className="cart-saved-n">{savedCount}</span>
          </button>
        )}

        {lines.length === 0 ? (
          <div className="cart-empty">
            <ShoppingBag size={28} strokeWidth={1.4} />
            <p>{t("cartEmpty")}</p>
            <button className="btn-ghost" onClick={onClose}>
              {t("browse")}
            </button>
          </div>
        ) : (
          <>
            <div className="drawer-body">
              {lines.map((l) => (
                <div className="cart-line" key={l.id}>
                  <div className="cart-thumb">
                    <ProductArt art={l.product.art} small />
                  </div>
                  <div className="cart-l-info">
                    <div className="cart-l-top">
                      <span className="cart-l-name">{l.product.name}</span>
                      <div className="cart-l-acts">
                        {/* Mettre de cote plutot que supprimer : l'article
                            quitte le total sans quitter la memoire. */}
                        <button
                          className="link-del"
                          onClick={() => onSaveForLater(l.id)}
                          aria-label={t("saveForLater")}
                          title={t("saveForLater")}
                        >
                          <Bookmark size={15} />
                        </button>
                        <button
                          className="link-del"
                          onClick={() => onRemove(l.id)}
                          aria-label={t("removeC")}
                          title={t("removeC")}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                    <span className="mono small muted">{l.product.code}</span>
                    <div className="cart-l-bot">
                      <div className="stepper">
                        <button onClick={() => onQty(l.id, l.qty - 1)} aria-label="-">
                          <Minus size={14} />
                        </button>
                        <span>{l.qty}</span>
                        <button
                          onClick={() => onQty(l.id, l.qty + 1)}
                          aria-label="+"
                          disabled={l.qty >= l.product.stock}
                        >
                          <Plus size={14} />
                        </button>
                      </div>
                      <span className="mono price">{eur(l.product.price_cents * l.qty)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="drawer-ft">
              <PromoField
                promo={promo}
                promoLabel={promoLabel}
                onApply={onApplyPromo}
                onClear={onClearPromo}
              />
              <div className="sum-row">
                <span>{t("subtotal")}</span>
                <span className="mono">{eur(disp.subtotal_cents)}</span>
              </div>
              {disp.discount_cents > 0 && (
                <div className="sum-row disc">
                  <span>{t("discount")}</span>
                  <span className="mono">−{eur(disp.discount_cents)}</span>
                </div>
              )}
              <div className="sum-row">
                <span>{t("shipping")}</span>
                <span className="mono">
                  {disp.shipping_cents === 0 ? t("free") : eur(disp.shipping_cents)}
                </span>
              </div>
              <ShippingGauge
                subtotalCents={disp.subtotal_cents}
                discountCents={disp.discount_cents}
                eur={eur}
              />
              <div className="sum-row total">
                <span>{t("total")}</span>
                <span className="mono">{eur(disp.total_cents)}</span>
              </div>
              <div className="drawer-delivery">
                <DeliveryNote lang={lang} />
              </div>
              <button className="btn-primary full" onClick={onCheckout}>
                {t("checkout")} <ArrowRight size={17} />
              </button>
              <button className="btn-ghost full" onClick={onClose}>
                {t("continueShop")}
              </button>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
