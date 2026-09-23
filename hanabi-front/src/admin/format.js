/** Mise en forme partagee par les ecrans du back-office (francais seul). */
import { createPriceFormatter } from "../lib/format.js";

export const eur = createPriceFormatter("fr");

export const fmtDate = (s) =>
  new Date(s).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });

export const decimale = (v, chiffres = 1) =>
  Number(v).toLocaleString("fr-FR", {
    minimumFractionDigits: chiffres,
    maximumFractionDigits: chiffres,
  });

export const pct = (v, chiffres = 1) => `${decimale(v * 100, chiffres)} %`;

export const num = (v) => (v ?? 0).toLocaleString("fr-FR");

/** Accord a partir de deux : « 0 produit », « 1 produit », « 2 produits ». */
export const pluriel = (n, mot) => `${num(n)} ${mot}${n > 1 ? "s" : ""}`;

/** « il y a 3 h » plutot qu'un horodatage a soustraire de tete. */
export function anciennete(iso) {
  if (!iso) return "jamais";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 2) return "à l'instant";
  return `il y a ${dureeCourte(minutes)}`;
}

/** « 2 min », « 3 h », « 2 j », avec espace insécable. */
export function dureeCourte(minutes) {
  if (minutes < 60) return `${Math.round(minutes)}\u00a0min`;
  if (minutes < 1440) return `${Math.round(minutes / 60)}\u00a0h`;
  return `${Math.round(minutes / 1440)}\u00a0j`;
}

/** Libelle d'infobulle des commandes desactivees pour le compte de
 *  demonstration. Le refus reel vient du serveur. */
export const LECTURE_SEULE = "Compte de démonstration : modification désactivée";

/** Libellés des statuts. Les passages permis viennent du serveur (`next`), qui les applique. */
export const STATUS_LABELS = {
  pending: "En attente",
  paid: "Payée",
  shipped: "Expédiée",
  delivered: "Livrée",
  cancelled: "Annulée",
  refunded: "Remboursée",
};
