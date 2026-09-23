/** Panier : panneau a droite sur grand ecran, feuille basse sur telephone. */
import { X, Minus, Plus, ArrowRight } from "lucide-react";
import { PictoGarde, PictoPanier } from "../brand/Pictos.jsx";
import { useT } from "../../i18n/context.jsx";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";
import { ProductArt } from "../brand/ProductArt.jsx";
import { DeliveryNote } from "../ui/DeliveryNote.jsx";
import { PromoField } from "./PromoField.jsx";
import { ShippingGauge } from "./ShippingGauge.jsx";
import { Totals } from "./Totals.jsx";

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
  const ref = useFocusTrap(open);
  const articles = lines.reduce((s, l) => s + l.qty, 0);

  return (
    <>
      <div className="scrim" data-open={open} onClick={onClose} aria-hidden="true" />
      <aside
        ref={ref}
        className="sheet sheet-cart"
        data-open={open}
        role="dialog"
        aria-modal="true"
        aria-labelledby="panier-titre"
        inert={open ? undefined : ""}
      >
        <div className="sheet-head">
          <h2 id="panier-titre">
            {t("cart")}
            {articles > 0 && <span className="sheet-count">{t("itemsN", { n: articles })}</span>}
          </h2>
          <button className="icon-btn" onClick={onClose} aria-label={t("close")}>
            <X size={20} />
          </button>
        </div>

        {savedCount > 0 && (
          <button className="cart-saved" onClick={onGoSaved}>
            <PictoGarde taille={16} /> {t("saved")}
            <span className="cart-saved-count">{savedCount}</span>
          </button>
        )}

        {lines.length === 0 ? (
          <div className="sheet-body empty">
            <PictoPanier taille={32} />
            <h3>{t("cartEmptyTitle")}</h3>
            <p>{t("cartEmpty")}</p>
            <button className="btn btn-quiet" onClick={onClose}>
              {t("browse")}
            </button>
          </div>
        ) : (
          <>
            <div className="sheet-body">
              <ul className="lines">
                {lines.map((l) => (
                  <li className="line" key={l.id}>
                    <span className="line-art">
                      <ProductArt art={l.product.art} />
                    </span>
                    <div className="line-main">
                      <div className="line-top">
                        <p className="line-name">{l.product.name}</p>
                        <span className="price">{eur(l.product.price_cents * l.qty)}</span>
                      </div>
                      <span className="code">{l.product.code}</span>
                      <div className="line-actions">
                        <div
                          className="stepper"
                          role="group"
                          aria-label={t("qtyOf", { name: l.product.name })}
                        >
                          <button
                            onClick={() => onQty(l.id, l.qty - 1)}
                            aria-label={t("qtyLess")}
                            disabled={l.qty <= 1}
                          >
                            <Minus size={16} />
                          </button>
                          <output aria-live="polite">{l.qty}</output>
                          <button
                            onClick={() => onQty(l.id, l.qty + 1)}
                            aria-label={t("qtyMore")}
                            disabled={l.qty >= l.product.stock}
                          >
                            <Plus size={16} />
                          </button>
                        </div>
                        <button className="link" onClick={() => onSaveForLater(l.id)}>
                          {t("saveForLater")}
                        </button>
                        <button className="link" onClick={() => onRemove(l.id)}>
                          {t("removeC")}
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
              <ShippingGauge
                subtotalCents={disp.subtotal_cents}
                discountCents={disp.discount_cents}
                eur={eur}
              />
              <PromoField
                promo={promo}
                promoLabel={promoLabel}
                onApply={onApplyPromo}
                onClear={onClearPromo}
              />
            </div>
            <div className="sheet-foot">
              <Totals disp={disp} eur={eur} />
              <DeliveryNote lang={lang} />
              <button className="btn btn-primary btn-block" onClick={onCheckout}>
                {t("checkout")} <ArrowRight size={18} aria-hidden="true" />
              </button>
            </div>
          </>
        )}
      </aside>
    </>
  );
}
