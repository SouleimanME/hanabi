/** Budget de poids : la construction ECHOUE si le site grossit trop.
 *
 * POURQUOI UN BUDGET PLUTOT QU'UNE MESURE. Un chiffre affiche en fin de
 * construction ne change rien : on le lit une fois, on l'oublie, et le poids
 * monte de trois kilo-octets par semaine sans qu'aucune journee ne soit
 * fautive. Un budget transforme cette derive en decision - depasser demande de
 * relever le plafond, donc de l'assumer et de l'ecrire.
 *
 * CE QUI EST MESURE : le transfert compresse (gzip), pas la taille sur disque.
 * C'est ce qui traverse le reseau, donc ce que quelqu'un attend. Comparer des
 * tailles non compressees donnerait des chiffres trois fois plus gros et sans
 * rapport avec l'experience.
 *
 * LES PLAFONDS sont poses juste au-dessus du poids constate, arrondis au
 * kilo-octet superieur d'une marge deliberement etroite : un budget large ne
 * signale jamais rien. Ils ne sont pas des objectifs de performance, ce sont
 * des DETECTEURS DE DERIVE.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

const DIST = "dist/assets";

/* Plafonds en kilo-octets compresses.
 *
 * MESURES, PUIS ARRONDIS AVEC ENVIRON 12 % DE MARGE. Ils ne sortent pas d'une
 * intuition : la premiere execution de ce script a donne 45,4 / 55,9 / 24,2 /
 * 19,2 ko, et les plafonds se posent juste au-dessus. Un budget devine trop
 * large ne signale jamais rien - j'avais estime le back-office a 90 ko, il en
 * fait 24.
 *
 * `index` : React et le socle, charges par tout le monde - y compris quelqu'un
 *           qui ne verra qu'une fiche produit. C'est le lot qui compte le plus.
 * `App`   : la boutique elle-meme.
 * `Admin` : le back-office. Charge A LA DEMANDE, jamais par un visiteur : son
 *           poids ne coute rien au tunnel d'achat.
 * `css`   : toutes les feuilles reunies.
 */
const BUDGETS = {
  index: 51,
  App: 63,
  Admin: 28,
  css: 22,
};

/** Nom de lot d'un fichier construit : `App-C1d3SgQA.js` devient `App`. */
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
    // Un lot attendu qui disparait est aussi une derive : un decoupage modifie
    // sans que le budget suive, et la surveillance s'arrete en silence.
    depassements.push(`  ${nom} : lot introuvable dans ${DIST}`);
    continue;
  }
  const part = Math.round((poids / plafond) * 100);
  const etat = poids > plafond ? "DEPASSE" : part > 90 ? "au bord" : "ok";
  lignes.push(
    `  ${nom.padEnd(8)} ${poids.toFixed(1).padStart(6)} ko / ${plafond} ko  (${part} %) ${etat}`,
  );
  if (poids > plafond) {
    depassements.push(
      `  ${nom} : ${poids.toFixed(1)} ko compresses pour un plafond de ${plafond} ko`,
    );
  }
}

// Les lots non budgetes sont listes sans jugement : ils viennent du decoupage
// automatique de Vite et changent de nom au fil des versions.
const horsBudget = Object.keys(parLot).filter((n) => !(n in BUDGETS));
if (horsBudget.length) {
  lignes.push(
    `  (hors budget : ${horsBudget.map((n) => `${n} ${parLot[n].toFixed(1)} ko`).join(", ")})`,
  );
}

console.log("\nPoids transfere (gzip)\n" + lignes.join("\n"));

if (depassements.length) {
  console.error(
    "\nBudget de poids depasse :\n" +
      depassements.join("\n") +
      "\n\nDeux issues, et le choix doit etre explicite :\n" +
      "  - alleger (import a la demande, dependance retiree) ;\n" +
      "  - relever le plafond dans scripts/budget.js, en disant pourquoi.\n",
  );
  process.exit(1);
}

console.log("\nTous les lots sont dans leur budget.\n");
