/** Carte produit de la grille de la selection.
 *
 * La carte est concue pour donner envie de cliquer : elle s'incline en 3D sous
 * le curseur (useTilt), un reflet balaye le visuel, et elle apparait en fondu
 * quand elle entre dans le champ de vision (useReveal), decalee selon son rang
 * pour un effet de cascade. L'ajout au panier declenche une gerbe d'etincelles
 * a l'endroit du clic - le petit plaisir qui transforme un achat en geste.
 */
import { memo } from "react";
import { Plus, Heart, Eye } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { ProductArt } from "../brand/ProductArt.jsx";
import { Stars } from "../ui/Stars.jsx";
import { StockBadge } from "../ui/StockBadge.jsx";
import { useReveal } from "../../hooks/useReveal.js";
import { useTilt } from "../../hooks/useTilt.js";
import { burstFromElement } from "../../lib/burst.js";

export const ProductCard = memo(function ProductCard({
  p,
  onOpen,
  onAdd,
  wished,
  onWish,
  eur,
  index = 0,
}) {
  const t = useT();
  const [revealRef, visible] = useReveal();
  const tilt = useTilt();

  const handleAdd = (e) => {
    burstFromElement(e.currentTarget);
    onAdd(p.id);
  };

  // Enveloppe et carte portent chacune leur transform : l'enveloppe anime
  // l'apparition (translation lente), la carte l'inclinaison (rotation rapide).
  // Les melanger sur un seul noeud ferait bouger le tilt a la vitesse du fondu.
  return (
    <div
      ref={revealRef}
      className={"card-wrap reveal" + (visible ? " in" : "")}
      style={{ transitionDelay: `${Math.min(index, 8) * 55}ms` }}
    >
      <article
        ref={tilt.ref}
        className="card"
        onMouseEnter={tilt.onMouseEnter}
        onMouseMove={tilt.onMouseMove}
        onMouseLeave={tilt.onMouseLeave}
      >
        <button className="card-art" onClick={() => onOpen(p)} aria-label={p.name}>
          <ProductArt art={p.art} />
          <span className="card-sheen" aria-hidden="true" />
          <span className="card-cat">{t("cat_" + p.category)}</span>
          {p.is_new && <span className="card-new">{t("neuf")}</span>}
          <span className="card-peek">
            <Eye size={15} /> {t("discover")}
          </span>
        </button>
        <button
          className={"wish" + (wished ? " on" : "")}
          onClick={(e) => {
            if (!wished) burstFromElement(e.currentTarget, { count: 14, power: 5 });
            onWish(p.id);
          }}
          aria-label="Favori"
          aria-pressed={wished}
        >
          <Heart size={17} fill={wished ? "currentColor" : "none"} />
        </button>
        <div className="card-body">
          <div className="card-top">
            <span className="mono small muted">{p.code}</span>
            <span className="mono price">{eur(p.price_cents)}</span>
          </div>
          <button className="card-name" onClick={() => onOpen(p)}>
            {p.name}
          </button>
          <div className="card-rate">
            <Stars value={p.rating_avg} count={p.rating_count} />
          </div>
          <p className="card-blurb">{p.blurb}</p>
          <div className="card-foot">
            <StockBadge stock={p.stock} />
            <button className="btn-add" onClick={handleAdd} disabled={p.stock === 0}>
              {p.stock === 0 ? (
                t("sold")
              ) : (
                <>
                  <Plus size={15} strokeWidth={2.5} /> {t("add")}
                </>
              )}
            </button>
          </div>
        </div>
      </article>
    </div>
  );
});
