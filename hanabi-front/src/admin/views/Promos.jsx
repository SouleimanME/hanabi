/** Codes promo. */
import { useState } from "react";
import { Plus } from "lucide-react";

import { api } from "../api.js";
import { eur, fmtDate, LECTURE_SEULE } from "../format.js";

const VIDE = {
  code: "",
  kind: "percent",
  percent: 10,
  amount_cents: 500,
  min_subtotal_cents: 0,
  active: true,
  expires_at: "",
};

const TYPES = { percent: "Pourcentage", fixed: "Montant fixe", free_shipping: "Port offert" };

export function Promos({ items, flash, reload, readonly }) {
  const [form, setForm] = useState(null);
  const [f, setF] = useState(VIDE);
  const set = (k) => (e) =>
    setF((s) => ({ ...s, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const save = async (e) => {
    e.preventDefault();
    try {
      const body = {
        ...f,
        percent: f.kind === "percent" ? parseInt(f.percent, 10) : null,
        amount_cents: f.kind === "fixed" ? parseInt(f.amount_cents, 10) : null,
        min_subtotal_cents: parseInt(f.min_subtotal_cents, 10) || 0,
        expires_at: f.expires_at || null,
      };
      if (form?.id) await api(`/admin/promos/${form.id}`, { method: "PATCH", body });
      else await api("/admin/promos", { method: "POST", body });
      flash(form?.id ? "Code mis à jour" : "Code créé");
      setForm(null);
      reload();
    } catch (err) {
      flash(err.message, "err");
    }
  };

  const del = async (p) => {
    if (!confirm(`Supprimer le code ${p.code} ?`)) return;
    try {
      await api(`/admin/promos/${p.id}`, { method: "DELETE" });
      flash("Code supprimé");
      reload();
    } catch (err) {
      flash(err.message, "err");
    }
  };

  const ouvrir = (p) => {
    setForm(p || {});
    setF(
      p
        ? {
            code: p.code,
            kind: p.kind,
            percent: p.percent || 10,
            amount_cents: p.amount_cents || 500,
            min_subtotal_cents: p.min_subtotal_cents || 0,
            active: p.active,
            expires_at: p.expires_at?.slice(0, 10) || "",
          }
        : VIDE,
    );
  };

  return (
    <div>
      <div className="adm-toolbar">
        <button
          className="adm-btn primary"
          disabled={readonly}
          title={readonly ? LECTURE_SEULE : undefined}
          onClick={() => ouvrir(null)}
        >
          <Plus size={16} aria-hidden="true" /> Nouveau code
        </button>
      </div>

      {form !== null && (
        <div className="adm-modal-wrap">
          <div className="adm-modal-voile" onClick={() => setForm(null)} aria-hidden="true" />
          <form
            className="adm-modal"
            onSubmit={save}
            role="dialog"
            aria-modal="true"
            aria-labelledby="promo-titre"
            onKeyDown={(e) => e.key === "Escape" && setForm(null)}
          >
            <h3 id="promo-titre">{form.id ? `Modifier ${form.code}` : "Nouveau code promo"}</h3>
            <label className="adm-field">
              <span>Code</span>
              <input
                value={f.code}
                onChange={set("code")}
                className="code-input"
                disabled={Boolean(form.id)}
                autoFocus
                required
              />
            </label>
            <label className="adm-field">
              <span>Type</span>
              <select value={f.kind} onChange={set("kind")}>
                <option value="percent">Pourcentage</option>
                <option value="fixed">Montant fixe</option>
                <option value="free_shipping">Port offert</option>
              </select>
            </label>
            {f.kind === "percent" && (
              <label className="adm-field">
                <span>Réduction en %</span>
                <input
                  type="number"
                  value={f.percent}
                  onChange={set("percent")}
                  min={1}
                  max={100}
                />
              </label>
            )}
            {f.kind === "fixed" && (
              <label className="adm-field">
                <span>Montant en centimes</span>
                <input
                  type="number"
                  value={f.amount_cents}
                  onChange={set("amount_cents")}
                  min={0}
                />
                <small className="num">{eur(f.amount_cents)}</small>
              </label>
            )}
            <label className="adm-field">
              <span>Minimum de commande en centimes</span>
              <input
                type="number"
                value={f.min_subtotal_cents}
                onChange={set("min_subtotal_cents")}
                min={0}
              />
              <small className="num">{eur(f.min_subtotal_cents)}</small>
            </label>
            <label className="adm-field">
              <span>Expire le (facultatif)</span>
              <input type="date" value={f.expires_at} onChange={set("expires_at")} />
            </label>
            <label className="adm-check">
              <input type="checkbox" checked={f.active} onChange={set("active")} /> Actif
            </label>
            <div className="adm-modal-actions">
              <button type="button" className="adm-btn" onClick={() => setForm(null)}>
                Annuler
              </button>
              <button type="submit" className="adm-btn primary">
                {form.id ? "Enregistrer" : "Créer"}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Code</th>
              <th scope="col">Type</th>
              <th scope="col" className="num">
                Valeur
              </th>
              <th scope="col" className="num">
                Minimum
              </th>
              <th scope="col">Expire</th>
              <th scope="col">Statut</th>
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id}>
                <td className="code">{p.code}</td>
                <td>{TYPES[p.kind]}</td>
                <td className="num">
                  {p.kind === "percent"
                    ? `${p.percent} %`
                    : p.kind === "fixed"
                      ? eur(p.amount_cents)
                      : "-"}
                </td>
                <td className="num">
                  {p.min_subtotal_cents > 0 ? eur(p.min_subtotal_cents) : "-"}
                </td>
                <td>{p.expires_at ? fmtDate(p.expires_at) : "Jamais"}</td>
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
                    onClick={() => ouvrir(p)}
                  >
                    Modifier
                  </button>
                  <button
                    className="adm-btn sm danger"
                    disabled={readonly}
                    title={readonly ? LECTURE_SEULE : undefined}
                    onClick={() => del(p)}
                  >
                    Supprimer
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
