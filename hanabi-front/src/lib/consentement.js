/** Choix du visiteur sur la mesure d'audience, gardé six mois comme le
 *  recommande la CNIL, puis redemandé. Une seule finalité soumise à accord :
 *  rattacher les fiches consultées au compte connecté. */
import { useSyncExternalStore } from "react";
import { storage } from "./storage.js";

const CLE = "consentement";
// Changer la liste des finalités oblige à redemander : le choix ancien ne les couvrait pas
export const VERSION = 1;
export const DUREE_MS = 182 * 24 * 60 * 60 * 1000;

const abonnes = new Set();
let courant = lire();

function lire(maintenant = Date.now()) {
  const choix = storage.get(CLE, null);
  if (!choix || choix.version !== VERSION || typeof choix.audience !== "boolean") return null;
  const le = Date.parse(choix.le);
  if (!Number.isFinite(le) || maintenant - le > DUREE_MS) return null;
  return choix;
}

/** Choix en cours, ou `null` s'il n'y en a pas encore (ou s'il a expiré). */
export const choixActuel = () => courant;

/** L'audience peut-elle être rattachée au compte ? Faux tant que rien n'est choisi. */
export const audienceAcceptee = () => courant?.audience === true;

export function enregistrerChoix({ audience }, maintenant = new Date()) {
  courant = { version: VERSION, audience: Boolean(audience), le: maintenant.toISOString() };
  storage.set(CLE, courant);
  abonnes.forEach((f) => f());
}

/** Relit le stockage : utile aux tests et au retour d'un autre onglet. */
export function relire(maintenant) {
  courant = lire(maintenant);
  abonnes.forEach((f) => f());
}

function abonner(f) {
  abonnes.add(f);
  return () => abonnes.delete(f);
}

export function useConsentement() {
  return useSyncExternalStore(abonner, choixActuel, choixActuel);
}
