/** Banque émettrice d'une carte, d'après ses six premiers chiffres (le BIN).
 *  La table vient de bin-list-data (CC BY 4.0, voir scripts/banques.js) et se
 *  lit dans le navigateur : aucun chiffre de la carte ne part pour la trouver.
 *  Chargée à la demande (6 ko compressés), elle ne pèse que sur le paiement. */
import { digitsOnly } from "./card.js";

// Préfixes des numéros de test des prestataires, ceux que la boutique propose
export const BIN_DE_TEST = new Set(["424242", "400000", "555555", "222300", "378282"]);
export const CARTE_DE_TEST = "test";

let table = null;

/** Charge la table une fois ; appeler tôt (au focus du champ) évite toute attente. */
export function chargerBanques() {
  table ||= import("../content/banques.json").then(({ default: json }) => {
    const parBin = new Map();
    for (const [nom, bins] of Object.entries(json)) {
      for (const bin of bins.split(" ")) parBin.set(bin, nom);
    }
    return parBin;
  });
  return table;
}

/** Nom de la banque (« A|B » quand le groupe émet pour deux enseignes),
 *  `CARTE_DE_TEST`, ou `null` si la table ne la connaît pas. */
export async function banqueDe(numero) {
  const bin = digitsOnly(numero).slice(0, 6);
  if (bin.length < 6) return null;
  if (BIN_DE_TEST.has(bin)) return CARTE_DE_TEST;
  return (await chargerBanques()).get(bin) ?? null;
}

/** « Crédit Mutuel|CIC » devient « Crédit Mutuel ou CIC », dans la langue affichée. */
export function nomDeBanque(nom, langue) {
  const enseignes = nom.split("|");
  if (enseignes.length === 1) return nom;
  return new Intl.ListFormat(langue, { type: "disjunction" }).format(enseignes);
}
