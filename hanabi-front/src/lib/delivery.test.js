/** Estimation de livraison.
 *
 * Toutes les dates sont figees. Une estimation calculee depuis `new Date()`
 * donnerait un test dont le resultat depend du jour ou on le lance : vert le
 * mardi, rouge le samedi, et impossible a reproduire quand il casse.
 */
import { describe, it, expect } from "vitest";

import { CUTOFF_HOUR, isBeforeCutoff, estimateDelivery, formatDeliveryDate } from "./delivery.js";

// Aout 2026 : le 3 est un lundi, le 8 un samedi, le 9 un dimanche.
const lundi = (h = 9) => new Date(2026, 7, 3, h, 0, 0);
const vendredi = (h = 9) => new Date(2026, 7, 7, h, 0, 0);
const samedi = (h = 9) => new Date(2026, 7, 8, h, 0, 0);
const dimanche = (h = 9) => new Date(2026, 7, 9, h, 0, 0);

const jour = (d) => ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"][d.getDay()];

describe("isBeforeCutoff", () => {
  it("est vrai avant l'heure limite un jour ouvre", () => {
    expect(isBeforeCutoff(lundi(CUTOFF_HOUR - 1))).toBe(true);
  });

  it("est faux a l'heure limite pile", () => {
    // La borne est stricte : a 15 h 00, la preparation du jour est close.
    expect(isBeforeCutoff(lundi(CUTOFF_HOUR))).toBe(false);
  });

  it("est faux le week-end, meme au petit matin", () => {
    expect(isBeforeCutoff(samedi(8))).toBe(false);
    expect(isBeforeCutoff(dimanche(8))).toBe(false);
  });
});

describe("estimateDelivery", () => {
  it("ne tombe jamais un week-end", () => {
    // La propriete qui compte : quel que soit le point de depart, la date
    // annoncee doit etre un jour ou quelqu'un peut reellement livrer.
    for (let j = 0; j < 60; j++) {
      for (const h of [8, 14, 15, 20]) {
        const depart = new Date(2026, 7, 1 + j, h, 0, 0);
        const arrivee = estimateDelivery(depart);
        expect([0, 6]).not.toContain(arrivee.getDay());
      }
    }
  });

  it("est toujours posterieure au depart", () => {
    for (let j = 0; j < 60; j++) {
      const depart = new Date(2026, 7, 1 + j, 10, 0, 0);
      expect(estimateDelivery(depart).getTime()).toBeGreaterThan(depart.getTime());
    }
  });

  it("livre jeudi pour une commande du lundi matin", () => {
    // Preparation le jour meme (1 j) + 2 j de transport = jeudi.
    const d = estimateDelivery(lundi(9));
    expect(jour(d)).toBe("jeu");
    expect(d.getDate()).toBe(6);
  });

  it("decale d'un jour ouvre une commande passee apres l'heure limite", () => {
    const avant = estimateDelivery(lundi(CUTOFF_HOUR - 1));
    const apres = estimateDelivery(lundi(CUTOFF_HOUR + 1));
    expect(apres.getTime()).toBeGreaterThan(avant.getTime());
    expect(jour(apres)).toBe("ven");
  });

  it("enjambe le week-end pour une commande du vendredi apres-midi", () => {
    // Vendredi 17 h : preparation lundi et mardi, transport mercredi et jeudi.
    const d = estimateDelivery(vendredi(17));
    expect(jour(d)).toBe("jeu");
    expect(d.getDate()).toBe(13);
  });

  it("donne la meme date pour le samedi et le dimanche", () => {
    // Aucune preparation n'a lieu le week-end : les deux repartent du lundi.
    expect(estimateDelivery(samedi()).getTime()).toBe(estimateDelivery(dimanche()).getTime());
  });

  it("est monotone : commander plus tard ne livre jamais plus tot", () => {
    let precedent = 0;
    for (let h = 0; h < 24 * 14; h++) {
      const arrivee = estimateDelivery(new Date(2026, 7, 3, h, 0, 0)).getTime();
      expect(arrivee).toBeGreaterThanOrEqual(precedent);
      precedent = arrivee;
    }
  });
});

describe("formatDeliveryDate", () => {
  const jeudi6 = new Date(2026, 7, 6, 12, 0, 0);

  it("ecrit la date dans la langue affichee", () => {
    expect(formatDeliveryDate(jeudi6, "fr")).toBe("jeudi 6 août");
    expect(formatDeliveryDate(jeudi6, "en")).toBe("Thursday, August 6");
  });

  it("omet l'annee, qui n'apporte rien a quatre jours", () => {
    for (const langue of ["fr", "en", "es"]) {
      expect(formatDeliveryDate(jeudi6, langue)).not.toMatch(/2026/);
    }
  });
});
