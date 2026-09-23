/** Choix sur la mesure d'audience : gardé six mois, jamais présumé. */
import { describe, it, expect, beforeEach } from "vitest";

import {
  audienceAcceptee,
  choixActuel,
  enregistrerChoix,
  relire,
  DUREE_MS,
  VERSION,
} from "./consentement.js";
import { storage } from "./storage.js";

beforeEach(() => {
  window.localStorage.clear();
  relire();
});

describe("sans choix", () => {
  it("ne rattache rien tant que le visiteur n'a pas répondu", () => {
    expect(choixActuel()).toBeNull();
    expect(audienceAcceptee()).toBe(false);
  });
});

describe("choix enregistré", () => {
  it("garde un accord", () => {
    enregistrerChoix({ audience: true });
    expect(audienceAcceptee()).toBe(true);
    expect(storage.get("consentement").version).toBe(VERSION);
  });

  it("garde un refus, qui compte autant qu'un accord", () => {
    enregistrerChoix({ audience: false });
    expect(choixActuel()).not.toBeNull();
    expect(audienceAcceptee()).toBe(false);
  });

  it("survit à un rechargement de la page", () => {
    enregistrerChoix({ audience: true });
    relire();
    expect(audienceAcceptee()).toBe(true);
  });
});

describe("expiration", () => {
  it("redemande le choix au bout de six mois", () => {
    const le = new Date("2026-01-01T00:00:00Z");
    enregistrerChoix({ audience: true }, le);
    relire(le.getTime() + DUREE_MS - 1000);
    expect(audienceAcceptee()).toBe(true);
    relire(le.getTime() + DUREE_MS + 1000);
    expect(choixActuel()).toBeNull();
  });

  it("redemande quand les finalités ont changé", () => {
    storage.set("consentement", {
      version: VERSION - 1,
      audience: true,
      le: new Date().toISOString(),
    });
    relire();
    expect(choixActuel()).toBeNull();
  });

  it("ignore un choix illisible", () => {
    storage.set("consentement", { version: VERSION, audience: "oui", le: "hier" });
    relire();
    expect(choixActuel()).toBeNull();
  });
});
