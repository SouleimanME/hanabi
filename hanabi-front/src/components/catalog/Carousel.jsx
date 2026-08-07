/** Carrousel des produits mis en avant, avec defilement automatique.
 *
 * Le defilement se met en pause au survol pour ne pas deplacer une cible que
 * l'utilisateur s'apprete a cliquer.
 */
import { useState, useEffect, useCallback } from "react";
import { ArrowLeft, ArrowRight, Plus } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { ProductArt } from "../brand/ProductArt.jsx";
import { Stars } from "../ui/Stars.jsx";
import { burstFromElement } from "../../lib/burst.js";

export function Carousel({ items, onOpen, onAdd, eur }) {
  const t = useT();
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);
  const n = items.length;

  const go = useCallback((d) => setIdx((i) => (i + d + n) % n), [n]);

  useEffect(() => {
    if (paused || n <= 1) return;
    const id = setInterval(() => setIdx((i) => (i + 1) % n), 5000);
    return () => clearInterval(id);
  }, [paused, n]);

  if (n === 0) return null;

  return (
    <section
      className="carou"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      aria-label="Sélection mise en avant"
    >
      <div className="carou-track" style={{ transform: `translateX(-${idx * 100}%)` }}>
        {items.map((p) => {
          const isImg = p.art && (p.art.startsWith("http") || p.art.startsWith("data:"));
          return (
            <div className="carou-slide" key={p.id}>
              <div className="carou-visual" onClick={() => onOpen(p)}>
                {isImg ? (
                  <img src={p.art} alt={p.name} className="carou-img" />
                ) : (
                  <ProductArt art={p.art} />
                )}
              </div>
              <div className="carou-content">
                <span className="carou-eyebrow">{p.is_new ? t("neuf") : t("pieceMonth")}</span>
                <h2 className="carou-name">{p.name}</h2>
                <div className="carou-rate">
                  <Stars value={p.rating_avg} count={p.rating_count} />
                </div>
                <p className="carou-blurb">{p.blurb}</p>
                <div className="carou-foot">
                  <span className="mono carou-price">{eur(p.price_cents)}</span>
                  <div className="carou-actions">
                    <button className="btn-ghost sm" onClick={() => onOpen(p)}>
                      {t("discover")}
                    </button>
                    <button
                      className="btn-primary"
                      onClick={(e) => {
                        burstFromElement(e.currentTarget);
                        onAdd(p.id);
                      }}
                      disabled={p.stock === 0}
                    >
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
              </div>
            </div>
          );
        })}
      </div>

      {n > 1 && (
        <>
          <button className="carou-arrow left" onClick={() => go(-1)} aria-label="Précédent">
            <ArrowLeft size={20} />
          </button>
          <button className="carou-arrow right" onClick={() => go(1)} aria-label="Suivant">
            <ArrowRight size={20} />
          </button>
          <div className="carou-dots">
            {items.map((_, i) => (
              <button
                key={i}
                className={"carou-dot" + (i === idx ? " on" : "")}
                onClick={() => setIdx(i)}
                aria-label={`Slide ${i + 1}`}
              />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
