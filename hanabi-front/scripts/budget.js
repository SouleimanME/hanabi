/** Budget de poids : la construction échoue si un lot dépasse son plafond. */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

const DIST = "dist/assets";

// Kilo-octets compressés. `Admin` est chargé à la demande, jamais par un visiteur.
const BUDGETS = {
  index: 51,
  App: 63,
  Admin: 28,
  css: 22,
};

/** `App-C1d3SgQA.js` devient `App`. */
const lot = (fichier) => fichier.replace(/-[A-Za-z0-9_-]{8,}\.(js|css)$/, "");

function mesurer() {
  const parLot = {};
  let cssTotal = 0;

  for (const fichier of readdirSync(DIST)) {
    const chemin = join(DIST, fichier);
    if (!statSync(chemin).isFile()) continue;

    const compresse = gzipSync(readFileSync(chemin)).length / 1024;
    if (fichier.endsWith(".css")) {
      cssTotal += compresse;
    } else if (fichier.endsWith(".js")) {
      const nom = lot(fichier);
      parLot[nom] = (parLot[nom] || 0) + compresse;
    }
  }
  return { parLot, cssTotal };
}

const { parLot, cssTotal } = mesurer();
const mesures = { ...parLot, css: cssTotal };

const lignes = [];
const depassements = [];

for (const [nom, plafond] of Object.entries(BUDGETS)) {
  const poids = mesures[nom];
  if (poids === undefined) {
    // Lot renommé ou fusionné : la surveillance s'arrêterait sans bruit
    depassements.push(`  ${nom} : lot introuvable dans ${DIST}`);
    continue;
  }
  const part = Math.round((poids / plafond) * 100);
  const etat = poids > plafond ? "DÉPASSÉ" : part > 90 ? "au bord" : "ok";
  lignes.push(
    `  ${nom.padEnd(8)} ${poids.toFixed(1).padStart(6)} ko / ${plafond} ko  (${part} %) ${etat}`,
  );
  if (poids > plafond) {
    depassements.push(
      `  ${nom} : ${poids.toFixed(1)} ko compressés pour un plafond de ${plafond} ko`,
    );
  }
}

// Lots issus du découpage automatique de Vite, listés sans plafond
const horsBudget = Object.keys(parLot).filter((n) => !(n in BUDGETS));
if (horsBudget.length) {
  lignes.push(
    `  (hors budget : ${horsBudget.map((n) => `${n} ${parLot[n].toFixed(1)} ko`).join(", ")})`,
  );
}

console.log("\nPoids transféré (gzip)\n" + lignes.join("\n"));

if (depassements.length) {
  console.error(
    "\nBudget de poids dépassé :\n" +
      depassements.join("\n") +
      "\n\nAlléger (import à la demande, dépendance retirée) ou relever le plafond\n" +
      "dans scripts/budget.js en indiquant pourquoi.\n",
  );
  process.exit(1);
}

console.log("\nTous les lots sont dans leur budget.\n");
