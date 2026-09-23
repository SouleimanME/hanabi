/** Client HTTP du back-office. Chaque route /admin est verifiee cote serveur ;
 *  ce client ne fait que joindre le jeton de la boutique. */
import { API_BASE, getToken, messageDeValidation } from "../lib/api.js";

/** Message lisible d'une réponse en erreur ; un refus de validation arrive en liste. */
function messageErreur(data, statut) {
  const detail = Array.isArray(data.detail) ? messageDeValidation(data.detail) : data.detail;
  return detail || `Erreur ${statut}`;
}

export async function api(path, opts = {}) {
  const token = getToken();
  const res = await fetch(API_BASE + path, {
    method: opts.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(messageErreur(data, res.status));
  return data;
}

/** Telecharge un fichier servi par une route protegee. */
export async function download(path, fallbackName) {
  const token = getToken();
  const res = await fetch(API_BASE + path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(messageErreur(data, res.status));
  }

  const match = (res.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/);
  const url = URL.createObjectURL(await res.blob());
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = match ? match[1] : fallbackName;
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  URL.revokeObjectURL(url);
}

/** Copie un texte ; si le navigateur refuse, selectionne le bloc pour Ctrl+C. */
export async function copierTexte(texte, flash, bloc) {
  try {
    await navigator.clipboard.writeText(texte);
    flash("Copié dans le presse-papiers");
  } catch {
    if (!bloc?.current) {
      flash("Copie refusée par le navigateur. Sélectionne le texte à la main.", "err");
      return;
    }
    const plage = document.createRange();
    plage.selectNodeContents(bloc.current);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(plage);
    flash("Texte sélectionné : Ctrl+C pour copier.");
  }
}
