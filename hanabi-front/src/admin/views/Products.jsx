/** Produits : liste, creation, modification, galerie. */
import { useState } from "react";
import { ArrowDown, ArrowUp, Plus, Upload, X } from "lucide-react";

import { api } from "../api.js";
import { eur, LECTURE_SEULE, pluriel } from "../format.js";
import { MAIN_SIZE, toCanonicalMain, toGalleryImage } from "../image.js";
import { ProductArt } from "../../components/brand/ProductArt.jsx";
import { FORMES, MATIERES, NOMS_FORMES } from "../../components/brand/formes.js";

const CATS = ["Figurines", "Décoration", "Luminaires"];
const ART_DEFAUT = "torii,#E0452A,#0A0605";

const estPhoto = (v) => Boolean(v) && (v.startsWith("http") || v.startsWith("data:"));

export function Products({ items, flash, reload, readonly }) {
  const [editing, setEditing] = useState(null); // null | "new" | produit
  const [saving, setSaving] = useState(false);

  const save = async (data) => {
    setSaving(true);
    try {
      if (data.id) {
        const res = await api(`/admin/products/${data.id}`, { method: "PATCH", body: data });
        const prevenus = res?.alertes_envoyees ?? 0;
        flash(
          prevenus
            ? `Produit mis à jour, ${prevenus} personne${prevenus > 1 ? "s" : ""} prévenue${prevenus > 1 ? "s" : ""} du retour en stock`
            : "Produit mis à jour",
        );
      } else {
        await api("/admin/products", { method: "POST", body: data });
        flash("Produit créé");
      }
      setEditing(null);
      reload();
    } catch (e) {
      flash(e.message, "err");
    } finally {
      setSaving(false);
    }
  };

  const del = async (p) => {
    if (!confirm(`Retirer « ${p.name} » du catalogue ?`)) return;
    try {
      const res = await api(`/admin/products/${p.id}`, { method: "DELETE" });
      // Un produit déjà vu, commandé ou noté reste en base, hors de la vente
      flash(
        res?.action === "supprime"
          ? `« ${p.name} » supprimé`
          : `« ${p.name} » retiré de la vente, gardé pour l'historique des commandes et des avis`,
      );
      reload();
    } catch (e) {
      flash(e.message, "err");
    }
  };

  if (editing !== null) {
    return (
      <ProductForm
        item={editing === "new" ? null : editing}
        onSave={save}
        onCancel={() => setEditing(null)}
        saving={saving}
      />
    );
  }

  return (
    <div>
      <div className="adm-toolbar">
        <button
          className="adm-btn primary"
          disabled={readonly}
          title={readonly ? LECTURE_SEULE : undefined}
          onClick={() => setEditing("new")}
        >
          <Plus size={16} aria-hidden="true" /> Nouveau produit
        </button>
        <span className="adm-count">
          {pluriel(items.filter((p) => p.active).length, "actif")} ·{" "}
          {pluriel(items.filter((p) => !p.active).length, "inactif")}
        </span>
      </div>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Visuel</th>
              <th scope="col">Code</th>
              <th scope="col">Nom</th>
              <th scope="col">Catégorie</th>
              <th scope="col" className="num">
                Prix
              </th>
              <th scope="col" className="num">
                Stock
              </th>
              <th scope="col">Statut</th>
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} className={p.active ? "" : "adm-row-off"}>
                <td>
                  <span className="adm-vignette">
                    <ProductArt art={p.art} />
                  </span>
                </td>
                <td className="code">{p.code}</td>
                <td>
                  <strong>{p.name}</strong>
                </td>
                <td>
                  <span className="adm-tag">{p.category}</span>
                </td>
                <td className="num">{eur(p.price_cents)}</td>
                <td className="num">
                  <span
                    className={
                      "stock-badge " + (p.stock === 0 ? "out" : p.stock <= 4 ? "low" : "ok")
                    }
                  >
                    {p.stock}
                  </span>
                </td>
                <td>
                  {p.active ? (
                    <span className="adm-tag ok">Actif</span>
                  ) : (
                    <span className="adm-tag off">Inactif</span>
                  )}
                </td>
                <td className="adm-actions">
                  <button
                    className="adm-btn sm"
                    disabled={readonly}
                    title={readonly ? LECTURE_SEULE : undefined}
                    onClick={() => setEditing(p)}
                  >
                    Modifier
                  </button>
                  <button
                    className="adm-btn sm danger"
                    disabled={readonly}
                    title={readonly ? LECTURE_SEULE : undefined}
                    onClick={() => del(p)}
                  >
                    Retirer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function lireDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (ev) => resolve(ev.target.result);
    reader.onerror = () => reject(new Error(`Lecture impossible : ${file.name}`));
    reader.readAsDataURL(file);
  });
}

const LANGUES = [
  { code: "en", nom: "Anglais" },
  { code: "es", nom: "Espagnol" },
];
const TRADUCTION_VIDE = { name: "", blurb: "", usages: "", alt: "" };

/* Une langue de la fiche : ce que lit un visiteur du site anglais ou espagnol */
function ChampsTraduction({ langue, nom, valeurs, onChange }) {
  const champ = (k) => (e) => onChange(langue, k, e.target.value);
  return (
    <fieldset className="adm-langue" lang={langue}>
      <legend>{nom}</legend>
      <label className="adm-field">
        <span>Nom</span>
        <input value={valeurs.name} onChange={champ("name")} maxLength={160} />
      </label>
      <label className="adm-field">
        <span>Description courte</span>
        <textarea value={valeurs.blurb} onChange={champ("blurb")} rows={2} maxLength={255} />
      </label>
      <label className="adm-field">
        <span>Usages</span>
        <textarea value={valeurs.usages} onChange={champ("usages")} rows={3} maxLength={1000} />
      </label>
      <label className="adm-field">
        <span>Texte alternatif de la photo</span>
        <input value={valeurs.alt} onChange={champ("alt")} maxLength={300} />
      </label>
    </fieldset>
  );
}

function ProductForm({ item, onSave, onCancel, saving }) {
  const [f, setF] = useState({
    id: item?.id,
    code: item?.code || "",
    name: item?.name || "",
    category: item?.category || "Figurines",
    blurb: item?.blurb || "",
    price_cents: item?.price_cents ?? 0,
    stock: item?.stock ?? 0,
    is_new: item?.is_new ?? false,
    active: item?.active ?? true,
    featured: item?.featured ?? false,
    featured_order: item?.featured_order ?? 0,
    art: estPhoto(item?.art) ? item.art : item?.art || ART_DEFAUT,
    images: item?.images || [],
    usages: item?.usages || "",
    alt: item?.alt || "",
    traductions: Object.fromEntries(
      LANGUES.map(({ code }) => [code, { ...TRADUCTION_VIDE, ...item?.traductions?.[code] }]),
    ),
  });
  const [imgInput, setImgInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState(null);

  const set = (k) => (e) =>
    setF((s) => ({ ...s, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const setNum = (k) => (e) => setF((s) => ({ ...s, [k]: parseInt(e.target.value, 10) || 0 }));
  const setTraduction = (langue, k, valeur) =>
    setF((s) => ({
      ...s,
      traductions: { ...s.traductions, [langue]: { ...s.traductions[langue], [k]: valeur } },
    }));

  const blason = estPhoto(f.art) ? ART_DEFAUT : f.art;
  const [forme, trace, fond] = blason.split(",");
  const poserBlason = (index, valeur) => {
    const parts = [forme, trace, fond];
    parts[index] = valeur;
    setF((s) => ({ ...s, art: parts.join(",") }));
  };

  const ajouterImage = () => {
    const v = imgInput.trim();
    if (!v) return;
    setF((s) => ({ ...s, images: [...s.images, v] }));
    setImgInput("");
  };
  const retirerImage = (i) => setF((s) => ({ ...s, images: s.images.filter((_, j) => j !== i) }));
  const deplacerImage = (i, dir) =>
    setF((s) => {
      const arr = [...s.images];
      const j = i + dir;
      if (j < 0 || j >= arr.length) return s;
      [arr[i], arr[j]] = [arr[j], arr[i]];
      return { ...s, images: arr };
    });
  const principale = (i) =>
    setF((s) => {
      const arr = [...s.images];
      const [choisie] = arr.splice(i, 1);
      return { ...s, images: [choisie, ...arr] };
    });

  /* Chaque photo est reduite avant d'entrer dans le formulaire. */
  const televerser = async (e) => {
    const fichiers = Array.from(e.target.files).filter((file) => file.type.startsWith("image/"));
    e.target.value = "";
    if (!fichiers.length) return;
    setUploadErr(null);
    setUploading(true);
    try {
      const prepares = [];
      for (const file of fichiers) prepares.push(await toGalleryImage(await lireDataUrl(file)));
      setF((s) => ({ ...s, images: [...s.images, ...prepares] }));
    } catch (error) {
      setUploadErr(error.message);
    } finally {
      setUploading(false);
    }
  };

  /* La premiere image devient le visuel principal ; une photo est recadree sur
     un carre fixe pour que toutes les fiches aient la meme resolution. */
  const enregistrer = async () => {
    const principaleImage = f.images[0];
    if (!estPhoto(principaleImage)) {
      onSave(f);
      return;
    }
    setUploadErr(null);
    try {
      onSave({ ...f, art: await toCanonicalMain(principaleImage) });
    } catch (error) {
      setUploadErr(`Visuel principal : ${error.message}`);
    }
  };

  return (
    <div className="adm-form-wrap">
      <div className="adm-form-head">
        <h2>{item ? `Modifier ${item.name}` : "Nouveau produit"}</h2>
        <button className="adm-btn" onClick={onCancel}>
          Annuler
        </button>
      </div>
      <div className="adm-form-grid">
        <div className="adm-col">
          <label className="adm-field">
            <span>Code produit</span>
            {/* Le code identifie l'objet dans les commandes passées : fixé à la création */}
            <input
              value={f.code}
              onChange={(e) => setF((s) => ({ ...s, code: e.target.value.toUpperCase() }))}
              placeholder="HNB-000"
              pattern="[A-Z0-9][A-Z0-9\-]{1,19}"
              readOnly={Boolean(item)}
              aria-describedby={item ? "code-fige" : undefined}
              required
            />
            {item && (
              <small id="code-fige" className="muted">
                Fixé à la création : il figure sur les commandes passées.
              </small>
            )}
          </label>
          <label className="adm-field">
            <span>Nom</span>
            <input value={f.name} onChange={set("name")} required />
          </label>
          <label className="adm-field">
            <span>Catégorie</span>
            <select value={f.category} onChange={set("category")}>
              {CATS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="adm-field">
            <span>Description courte</span>
            <textarea value={f.blurb} onChange={set("blurb")} rows={3} required />
          </label>
          <label className="adm-field">
            <span>Usages</span>
            <textarea
              value={f.usages}
              onChange={set("usages")}
              rows={4}
              maxLength={1000}
              aria-describedby="usages-aide"
              placeholder={"Veilleuse pour une chambre d'enfant\nCadeau de naissance"}
            />
            <small id="usages-aide" className="muted">
              Une ligne par usage : pièce, occasion, public. Invisibles sur la fiche, ils aident la
              recherche à trouver cet objet.
            </small>
          </label>
          <label className="adm-field">
            <span>Texte alternatif de la photo</span>
            <input
              value={f.alt}
              onChange={set("alt")}
              maxLength={300}
              aria-describedby="alt-aide"
              placeholder="Renard blanc en résine, assis, motifs rouges peints à la main"
            />
            <small id="alt-aide" className="muted">
              Ce que montre la photo principale, lu à qui ne la voit pas.
            </small>
          </label>
          <div className="adm-row2">
            <label className="adm-field">
              <span>Prix en centimes</span>
              <input type="number" value={f.price_cents} onChange={setNum("price_cents")} min={0} />
              <small className="num">{eur(f.price_cents)}</small>
            </label>
            <label className="adm-field">
              <span>Stock</span>
              <input type="number" value={f.stock} onChange={setNum("stock")} min={0} />
            </label>
          </div>
          <div className="adm-checks">
            <label>
              <input type="checkbox" checked={f.is_new} onChange={set("is_new")} /> Marqué « Nouveau
              »
            </label>
            <label>
              <input type="checkbox" checked={f.active} onChange={set("active")} /> Visible dans la
              boutique
            </label>
            <label>
              <input type="checkbox" checked={f.featured} onChange={set("featured")} /> Mis en avant
              (pièce du mois)
            </label>
          </div>
          {f.featured && (
            <label className="adm-field adm-field-court">
              <span>Ordre de mise en avant</span>
              <input
                type="number"
                value={f.featured_order}
                onChange={setNum("featured_order")}
                min={0}
              />
              <small>0 passe en premier</small>
            </label>
          )}
        </div>

        <div className="adm-col">
          <fieldset className="adm-field">
            <legend>Blason</legend>
            <div className="art-builder">
              <div className="art-preview">
                <ProductArt art={blason} />
              </div>
              <div className="art-controls">
                <label className="adm-field sm">
                  <span>Forme</span>
                  <select value={forme} onChange={(e) => poserBlason(0, e.target.value)}>
                    {FORMES.map((s) => (
                      <option key={s} value={s}>
                        {NOMS_FORMES[s]}
                      </option>
                    ))}
                  </select>
                </label>
                {[
                  { index: 1, libelle: "Tracé", valeur: trace },
                  { index: 2, libelle: "Fond", valeur: fond },
                ].map((champ) => (
                  <div key={champ.index} className="adm-field sm">
                    <span id={`matiere-${champ.index}`}>{champ.libelle}</span>
                    <div
                      className="color-row"
                      role="radiogroup"
                      aria-labelledby={`matiere-${champ.index}`}
                    >
                      {MATIERES.map((m) => (
                        <button
                          key={m.hex}
                          type="button"
                          role="radio"
                          aria-checked={champ.valeur?.toUpperCase() === m.hex}
                          aria-label={m.nom}
                          title={m.nom}
                          className="color-swatch"
                          style={{ background: m.hex }}
                          onClick={() => poserBlason(champ.index, m.hex)}
                        />
                      ))}
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  className="adm-btn sm"
                  onClick={() => setF((s) => ({ ...s, images: [...s.images, blason] }))}
                >
                  Ajouter à la galerie
                </button>
              </div>
            </div>
          </fieldset>

          <div className="adm-field">
            <span>Galerie</span>
            <p className="img-hint">
              La première image est le visuel principal. Une photo y est recadrée sur un carré de{" "}
              {MAIN_SIZE} px ; les suivantes gardent leur cadrage.
            </p>
            <label className="img-upload-zone">
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={televerser}
                className="sr-only"
              />
              <span className="img-upload-inner">
                {uploading ? (
                  <span className="adm-spin" aria-label="Préparation des photos" />
                ) : (
                  <>
                    <Upload size={20} aria-hidden="true" />
                    <span>
                      Choisir des photos
                      <small>JPG, PNG ou WebP, plusieurs à la fois</small>
                    </span>
                  </>
                )}
              </span>
            </label>
            {uploadErr && (
              <div className="adm-err" role="alert">
                {uploadErr}
              </div>
            )}
            <ul className="img-list">
              {f.images.map((img, i) => (
                <li key={i} className={"img-item" + (i === 0 ? " is-main" : "")}>
                  <span className="adm-vignette">
                    <ProductArt art={img} />
                  </span>
                  <span className="img-libelle">
                    {i === 0 && <span className="adm-tag ok">Principale</span>}
                    <span className="code">
                      {estPhoto(img)
                        ? img.startsWith("data:")
                          ? "Photo téléversée"
                          : img.slice(0, 30) + "…"
                        : img}
                    </span>
                  </span>
                  <span className="img-actions">
                    <button
                      type="button"
                      className="adm-btn sm icone"
                      disabled={i === 0}
                      onClick={() => deplacerImage(i, -1)}
                      aria-label="Monter"
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      type="button"
                      className="adm-btn sm icone"
                      disabled={i === f.images.length - 1}
                      onClick={() => deplacerImage(i, 1)}
                      aria-label="Descendre"
                    >
                      <ArrowDown size={14} />
                    </button>
                    {i !== 0 && (
                      <button type="button" className="adm-btn sm" onClick={() => principale(i)}>
                        Principale
                      </button>
                    )}
                    <button
                      type="button"
                      className="adm-btn sm icone danger"
                      onClick={() => retirerImage(i)}
                      aria-label="Retirer de la galerie"
                    >
                      <X size={14} />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
            <div className="img-add-row">
              <label className="sr-only" htmlFor="img-url">
                Adresse d&apos;une image ou blason
              </label>
              <input
                id="img-url"
                value={imgInput}
                onChange={(e) => setImgInput(e.target.value)}
                placeholder="URL d'image ou blason (forme,tracé,fond)"
                onKeyDown={(e) => e.key === "Enter" && ajouterImage()}
              />
              <button type="button" className="adm-btn sm" onClick={ajouterImage}>
                Ajouter
              </button>
            </div>
          </div>
        </div>
      </div>

      <section className="adm-langues" aria-labelledby="traductions-titre">
        <h3 id="traductions-titre">Traductions</h3>
        <p className="muted">
          Un champ vide reprend l&apos;anglais, puis le français : une fiche traduite à moitié reste
          lisible.
        </p>
        <div className="adm-langues-grille">
          {LANGUES.map(({ code, nom }) => (
            <ChampsTraduction
              key={code}
              langue={code}
              nom={nom}
              valeurs={f.traductions[code]}
              onChange={setTraduction}
            />
          ))}
        </div>
      </section>

      <div className="adm-form-actions">
        <button
          className="adm-btn primary large"
          onClick={enregistrer}
          disabled={saving || uploading}
        >
          {saving ? "Enregistrement…" : item ? "Enregistrer les modifications" : "Créer le produit"}
        </button>
      </div>
    </div>
  );
}
