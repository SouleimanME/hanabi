/** CONTRAT ENTRE LES DEUX PILES.
 *
 * `src/lib/constants.js` duplique deux montants qui font autorite dans
 * `hanabi-back/app/pricing.py` : les frais de port et le seuil de gratuite. Son
 * commentaire d'en-tete reconnait le risque - « toute divergence doit etre
 * corrigee la-bas » - mais reconnaitre un risque ne le previent pas.
 *
 * La duplication est deliberee et se defend : l'interface doit afficher un
 * total credible avant meme que le reseau reponde, et la jauge « plus que 12 €
 * pour le port offert » ne peut pas attendre un aller-retour a chaque touche.
 * Ce qui ne se defend pas, c'est qu'elle derive sans bruit. Un seuil abaisse a
 * 60 € cote serveur et oublie ici afficherait « port offert » sur une commande
 * facturee 6,90 € de plus - le genre d'ecart qu'un client remarque avant
 * l'equipe.
 *
 * Ce test lit le fichier Python comme une source de verite. C'est volontairement
 * rustique : pas de schema partage a maintenir, pas d'etape de generation, et
 * aucune dependance ajoutee. La contrepartie est qu'il casse si `pricing.py` est
 * reecrit - ce qui est exactement le moment ou l'on veut etre prevenu.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { SHIPPING_CENTS, FREE_SHIPPING_CENTS } from "../lib/constants.js";

const ICI = dirname(fileURLToPath(import.meta.url));
const PRICING = resolve(ICI, "../../../hanabi-back/app/pricing.py");

/** Lit une constante entiere declaree au niveau du module Python. */
function constantePython(source, nom) {
  const trouve = source.match(new RegExp(`^${nom}\\s*=\\s*(\\d+)`, "m"));
  if (!trouve) throw new Error(`Constante "${nom}" introuvable dans pricing.py`);
  return Number(trouve[1]);
}

describe("regles commerciales partagees avec le backend", () => {
  it("trouve le module de tarification du serveur", () => {
    // Si ce test echoue, c'est que le backend a bouge : le chemin est a corriger
    // ici plutot que de desactiver la verification.
    expect(existsSync(PRICING), `attendu a ${PRICING}`).toBe(true);
  });

  const source = existsSync(PRICING) ? readFileSync(PRICING, "utf8") : "";

  it("applique les memes frais de port que le serveur", () => {
    expect(SHIPPING_CENTS).toBe(constantePython(source, "SHIPPING_CENTS"));
  });

  it("applique le meme seuil de port offert que le serveur", () => {
    expect(FREE_SHIPPING_CENTS).toBe(constantePython(source, "FREE_SHIPPING_THRESHOLD_CENTS"));
  });

  it("exprime les deux montants en centimes entiers", () => {
    // Le reste de l'application ne manipule jamais d'euros flottants ; une
    // valeur decimale glissee ici propagerait des arrondis jusqu'au total.
    expect(Number.isInteger(SHIPPING_CENTS)).toBe(true);
    expect(Number.isInteger(FREE_SHIPPING_CENTS)).toBe(true);
  });

  it("garde un seuil de gratuite superieur aux frais de port", () => {
    // Un seuil inferieur aux frais rendrait le port offert systematique et la
    // jauge du panier absurde.
    expect(FREE_SHIPPING_CENTS).toBeGreaterThan(SHIPPING_CENTS);
  });
});
