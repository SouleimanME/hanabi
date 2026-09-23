/** contrat entre les deux piles. */
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
