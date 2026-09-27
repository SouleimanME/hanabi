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
  const declinaisons = p.variantes || [];
  // « À partir de » seulement si les couleurs n'ont pas toutes le même prix
  const prixVariables = new Set(declinaisons.map((v) => v.price_cents)).size > 1;

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
        <ProductArt
          art={p.art}
          taille="(min-width: 76rem) 25rem, (min-width: 60rem) 33vw, (min-width: 34rem) 50vw, 100vw"
        />
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
        {declinaisons.length > 1 && (
          <ul className="case-teintes" aria-label={t("variantsN", { n: declinaisons.length })}>
            {declinaisons.slice(0, 6).map((v) => (
              <li
                key={v.id}
                title={v.libelle}
                style={v.couleur ? { background: v.couleur } : undefined}
                className={v.couleur ? undefined : "sans-teinte"}
              >
                <span className="sr-only">{v.libelle}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="case-foot">
          <span className="price">
            {prixVariables ? t("fromPrice", { price: eur(p.price_cents) }) : eur(p.price_cents)}
          </span>
          <button
            className="btn btn-quiet btn-sm case-add"
            onClick={declinaisons.length ? () => onOpen(p) : ajouter}
            disabled={epuise}
            aria-label={
              epuise
                ? undefined
                : declinaisons.length
                  ? t("chooseNamed", { name: p.name })
                  : t("addNamed", { name: p.name })
            }
          >
            {epuise ? (
              t("sold")
            ) : declinaisons.length ? (
              t("choose")
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
