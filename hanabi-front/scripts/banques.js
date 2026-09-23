/** Table des banques émettrices, tirée de bin-list-data (venelinkochev, CC BY 4.0).
 *
 *    node scripts/banques.js <bin-list-data.csv>
 *
 *  Ne garde que Visa et Mastercard (American Express émet ses propres cartes)
 *  et les émetteurs que le client connaît sous ce nom. Un sous-traitant
 *  technique (Treezor, Contis, Mastercard France) inquiéterait au lieu de
 *  rassurer : sa carte reste sans banque affichée. */
import { readFileSync, writeFileSync } from "node:fs";

const SORTIE = "src/content/banques.json";
const RESEAUX = new Set(["VISA", "MASTERCARD"]);

// Nom affiché : noms exacts de la source. Un groupe qui émet pour deux
// enseignes les nomme toutes les deux (« A|B », lu « A ou B ») plutôt que
// d'en choisir une au hasard.
const NOMS = {
  "Crédit Agricole": [
    "CREDIT AGRICOLE, S.A.",
    "CREDIT AGRICOLE SOCIETE ANONYME",
    "CAISSE NATIONALE DE CREDIT AGRICOLE",
  ],
  LCL: ["LCL BANQUE", "LE CREDIT LYONNAIS"],
  "Banque Populaire|Caisse d'Épargne": ["BPCE", "GROUPE BPCE", "NATIXIS", "NATIXIS SA"],
  "Caisse d'Épargne": [
    "CAISSE NATIONALE DES CAISSES D'EPARGNE (CNCE)",
    "CAISSE NATIONALE DES CAISSES DEPARGNE (CNCE)",
    "CAISSE DEPARGNE",
    "CAISSE D'EPARGNE",
  ],
  "Banque Populaire": ["BANQUE POPULAIRE"],
  "Crédit Mutuel|CIC": [
    "BANQUE FEDERATIVE DU CREDIT MUTUEL (BFCM)",
    "BANQUE FEDERATIVE DU CREDIT MUTUEL",
    "CREDIT MUTUEL CMCIC",
  ],
  "Crédit Mutuel": [
    "CAISSE FEDERALE DE CREDIT MUTUEL",
    "CAISSE CENTRALE DE CREDIT MUTUEL",
    "CAISSE FEDERALE DU CREDIT MUTUEL DE MAINE-ANJOU ET DE BASSE-NORMANDIE",
    "CAISSE FEDERALE DU CREDIT MUTUEL OCEAN",
    "BANQUE EUROPEENNE DU CREDIT MUTUEL",
  ],
  "Crédit Mutuel Arkéa": ["CREDIT MUTUEL ARKEA"],
  CIC: [
    "CREDIT INDUSTRIEL ET COMMERCIAL",
    "LYONNAISE DE BANQUE",
    "BANQUE CIC EST",
    "CIC NORD OUEST",
    "BANQUE CIC SUD OUEST",
    "BANQUE CIC OUEST",
  ],
  "BNP Paribas": [
    "BNP PARIBAS",
    "BNP PARIBAS ANTILLES-GUYANE",
    "BNP PARIBAS REUNION",
    "BNP PARIBAS NOUVELLE CALEDONIE",
  ],
  "Société Générale": ["SOCIETE GENERALE, S.A.", "SOCIETE GENERALE"],
  "Crédit du Nord": ["CREDIT DU NORD"],
  "La Banque Postale": ["LA BANQUE POSTALE"],
  HSBC: ["HSBC CONTINENTAL EUROPE", "HSBC FRANCE", "HSBC"],
  CCF: ["CCF"],
  BoursoBank: ["BOURSORAMA BANQUE"],
  "Orange Bank": ["ORANGE BANK"],
  BforBank: ["BFORBANK, S.A."],
  Monabanq: ["MONABANQ."],
  Oney: ["ONEY BANK", "BANQUE ONEY, S.A."],
  "Carrefour Banque": ["CARREFOUR BANQUE"],
  "AXA Banque": ["AXA BANQUE"],
  "Allianz Banque": ["ALLIANZ BANQUE"],
  "Milleis Banque": ["MILLEIS BANQUE"],
  "Société Marseillaise de Crédit": ["SOCIETE MARSEILLAISE DE CREDIT"],
  "Ma French Bank": ["MA FRENCH BANK"],
  Lydia: ["LYDIA SOLUTIONS SAS"],
  Cofidis: ["COFIDIS"],
  Revolut: ["REVOLUT, LTD.", "REVOLUT BANK UAB"],
  Wise: ["WISE PAYMENTS, LTD.", "WISE EUROPE SA/NV"],
  N26: ["N26 BANK AG", "N26 GMBH"],
  bunq: ["BUNQ B.V."],
};

const AFFICHE = new Map(
  Object.entries(NOMS).flatMap(([nom, sources]) => sources.map((s) => [s, nom])),
);

/** Lecture CSV minimale : champs entre guillemets, virgules et guillemets doublés. */
function lignes(texte) {
  const sortie = [];
  let ligne = [];
  let champ = "";
  let cite = false;
  for (let i = 0; i < texte.length; i++) {
    const c = texte[i];
    if (cite) {
      if (c === '"' && texte[i + 1] === '"') {
        champ += '"';
        i++;
      } else if (c === '"') cite = false;
      else champ += c;
    } else if (c === '"') cite = true;
    else if (c === ",") {
      ligne.push(champ);
      champ = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && texte[i + 1] === "\n") i++;
      ligne.push(champ);
      sortie.push(ligne);
      ligne = [];
      champ = "";
    } else champ += c;
  }
  if (champ || ligne.length) sortie.push([...ligne, champ]);
  return sortie;
}

const source = process.argv[2];
if (!source) {
  console.error("Usage : node scripts/banques.js <bin-list-data.csv>");
  process.exit(1);
}

const [entete, ...donnees] = lignes(readFileSync(source, "utf8"));
const col = (nom) => entete.indexOf(nom);
const [iBin, iReseau, iEmetteur] = [col("BIN"), col("Brand"), col("Issuer")];

const parBin = new Map();
const ambigus = new Set();
for (const d of donnees) {
  const nom = AFFICHE.get(d[iEmetteur]?.trim());
  if (!nom || !RESEAUX.has(d[iReseau]) || !/^\d{6}$/.test(d[iBin])) continue;
  const deja = parBin.get(d[iBin]);
  // Deux émetteurs pour un même BIN : aucun des deux n'est sûr
  if (deja && deja !== nom) ambigus.add(d[iBin]);
  parBin.set(d[iBin], nom);
}
for (const bin of ambigus) parBin.delete(bin);

const banques = {};
for (const [bin, nom] of [...parBin].sort(([a], [b]) => a.localeCompare(b))) {
  (banques[nom] ||= []).push(bin);
}
const table = Object.fromEntries(
  Object.keys(banques)
    .sort((a, b) => a.localeCompare(b, "fr"))
    .map((nom) => [nom, banques[nom].join(" ")]),
);

writeFileSync(SORTIE, `${JSON.stringify(table, null, 2)}\n`);
console.log(`${parBin.size} BIN, ${Object.keys(table).length} banques → ${SORTIE}`);
