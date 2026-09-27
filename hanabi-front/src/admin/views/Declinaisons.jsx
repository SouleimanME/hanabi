/** Déclinaisons d'une fiche : une ligne par couleur, avec son prix, son stock
 *  et sa photo. Chargé à part, à l'ouverture d'une fiche. */
import { Plus, X } from "lucide-react";

import { estVideo } from "../../lib/images.js";

const VIDE = { libelle: "", couleur: "", price_cents: 0, stock: 0, image: "", traductions: {} };

/** « 11,80 » ou « 11.8 » en centimes ; NaN si illisible. */
function centimes(texte) {
  const propre = String(texte).trim().replace(/\s|€/g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(propre)) return NaN;
  return Math.round(Number(propre) * 100);
}

const enEuros = (c) => (c / 100).toFixed(2).replace(".", ",");

export default function Declinaisons({ valeur, onChange, images, prixObjet }) {
  const poser = (i, champ, v) =>
    onChange(valeur.map((d, j) => (j === i ? { ...d, [champ]: v } : d)));
  const traduire = (i, langue, v) =>
    onChange(
      valeur.map((d, j) =>
        j === i ? { ...d, traductions: { ...d.traductions, [langue]: v } } : d,
      ),
    );
  const photos = images.filter((img) => !estVideo(img) && /^(https?:|data:)/.test(img));

  return (
    <fieldset className="adm-field declinaisons-admin">
      <legend>Déclinaisons</legend>
      <p className="img-hint">
        Une couleur, son prix, son stock. Avec au moins une déclinaison, le prix et le stock de
        l&apos;objet en sont tirés : le plus bas, et la somme.
      </p>
      {valeur.map((d, i) => (
        <div key={d.id ?? `nouvelle-${i}`} className="declinaison-ligne">
          <label className="adm-field sm">
            <span>Libellé</span>
            <input
              value={d.libelle}
              onChange={(e) => poser(i, "libelle", e.target.value)}
              maxLength={60}
              placeholder="Noir"
              required
            />
          </label>
          <div className="adm-field sm">
            <span id={`teinte-${i}`}>Pastille</span>
            <div className="declinaison-teinte">
              <input
                type="color"
                aria-labelledby={`teinte-${i}`}
                value={d.couleur || "#000000"}
                onChange={(e) => poser(i, "couleur", e.target.value)}
              />
              {d.couleur && (
                <button
                  type="button"
                  className="adm-btn sm"
                  onClick={() => poser(i, "couleur", "")}
                >
                  Sans
                </button>
              )}
            </div>
          </div>
          <label className="adm-field sm">
            <span>Prix</span>
            <input
              inputMode="decimal"
              defaultValue={enEuros(d.price_cents)}
              onBlur={(e) => {
                const c = centimes(e.target.value);
                if (!Number.isNaN(c)) poser(i, "price_cents", c);
                e.target.value = enEuros(Number.isNaN(c) ? d.price_cents : c);
              }}
            />
          </label>
          <label className="adm-field sm">
            <span>Stock</span>
            <input
              type="number"
              min={0}
              value={d.stock}
              onChange={(e) => poser(i, "stock", Math.max(0, parseInt(e.target.value, 10) || 0))}
            />
          </label>
          <label className="adm-field sm">
            <span>Photo</span>
            <select value={d.image} onChange={(e) => poser(i, "image", e.target.value)}>
              <option value="">Celle de l&apos;objet</option>
              {photos.map((img, n) => (
                <option key={img} value={img}>
                  Vue {images.indexOf(img) + 1}
                  {n === 0 ? " (principale)" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="adm-field sm">
            <span>Anglais</span>
            <input
              value={d.traductions?.en || ""}
              onChange={(e) => traduire(i, "en", e.target.value)}
              maxLength={60}
              placeholder="Black"
            />
          </label>
          <label className="adm-field sm">
            <span>Espagnol</span>
            <input
              value={d.traductions?.es || ""}
              onChange={(e) => traduire(i, "es", e.target.value)}
              maxLength={60}
              placeholder="Negro"
            />
          </label>
          <button
            type="button"
            className="adm-btn sm icone"
            onClick={() => onChange(valeur.filter((_, j) => j !== i))}
            aria-label={`Retirer ${d.libelle || "cette déclinaison"}`}
          >
            <X size={14} />
          </button>
        </div>
      ))}
      <button
        type="button"
        className="adm-btn sm"
        onClick={() => onChange([...valeur, { ...VIDE, price_cents: prixObjet }])}
      >
        <Plus size={14} aria-hidden="true" /> Ajouter une déclinaison
      </button>
    </fieldset>
  );
}
