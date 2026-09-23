/** Case du plateau : un objet, son blason, son prix. */
import { memo, useEffect, useRef, useState } from "react";
import { Plus, Check } from "lucide-react";
import { PictoFavori } from "../brand/Pictos.jsx";
import { useT } from "../../i18n/context.jsx";
import { ProductArt } from "../brand/ProductArt.jsx";
import { StockBadge } from "../ui/StockBadge.jsx";

const DUREE_CONFIRMATION = 1600;

export const ProductCard = memo(function ProductCard({ p, onOpen, onAdd, wished, onWish, eur }) {
  const t = useT();
  const [ajoute, setAjoute] = useState(false);
  const minuteur = useRef(null);
  const epuise = p.stock === 0;

  useEffect(() => () => clearTimeout(minuteur.current), []);

  const ajouter = () => {
    onAdd(p.id);
    setAjoute(true);
    clearTimeout(minuteur.current);
    minuteur.current = setTimeout(() => setAjoute(false), DUREE_CONFIRMATION);
  };

  return (
    <li className={"case" + (epuise ? " is-out" : "")}>
      <div className="case-art">
        <ProductArt art={p.art} taille="(min-width: 72rem) 19rem, (min-width: 40rem) 33vw, 50vw" />
      </div>
      {p.is_new && <span className="case-new">{t("neuf")}</span>}
      {onWish && (
        <button
          className="fav"
          onClick={() => onWish(p.id)}
          aria-pressed={wished}
          aria-label={wished ? t("favRemove", { name: p.name }) : t("favAdd", { name: p.name })}
        >
          <PictoFavori taille={18} plein={wished} />
        </button>
      )}
      <div className="case-body">
        <div className="case-meta">
          <span className="code">{p.code}</span>
          <StockBadge stock={p.stock} quiet />
        </div>
        <h3 className="case-name">
          <button className="case-open" onClick={() => onOpen(p)}>
            {p.name}
          </button>
        </h3>
        <div className="case-foot">
          <span className="price">{eur(p.price_cents)}</span>
          <button
            className="btn btn-quiet btn-sm case-add"
            onClick={ajouter}
            disabled={epuise}
            aria-label={epuise ? undefined : t("addNamed", { name: p.name })}
          >
            {epuise ? (
              t("sold")
            ) : (
              <span className="swap" data-state={ajoute ? "done" : "idle"}>
                <span className="swap-idle">
                  <Plus size={15} strokeWidth={2.2} aria-hidden="true" /> {t("add")}
                </span>
                <span className="swap-done" aria-hidden="true">
                  <Check size={15} strokeWidth={2.2} /> {t("added")}
                </span>
              </span>
            )}
          </button>
        </div>
      </div>
    </li>
  );
});
