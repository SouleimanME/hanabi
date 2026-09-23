/** Adresses : ce qu'on garde de la réponse de la Base Adresse Nationale. */
import { afterEach, describe, it, expect, vi } from "vitest";

import { suggererAdresses, villesDuCodePostal } from "./adresses.js";

const reponse = (proprietes) =>
  vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ features: proprietes.map((properties) => ({ properties })) }),
  });

afterEach(() => vi.unstubAllGlobals());

describe("suggererAdresses", () => {
  it("rend rue, code postal et ville, sans les communes seules", async () => {
    vi.stubGlobal(
      "fetch",
      reponse([
        { id: "a", type: "housenumber", name: "8 Rue Mercière", postcode: "69002", city: "Lyon" },
        { id: "b", type: "municipality", name: "Lyon", postcode: "69001", city: "Lyon" },
      ]),
    );
    expect(await suggererAdresses("8 rue merc")).toEqual([
      { id: "a", adresse: "8 Rue Mercière", cp: "69002", ville: "Lyon" },
    ]);
  });

  it("n'interroge personne avant trois caractères", async () => {
    const appel = vi.fn();
    vi.stubGlobal("fetch", appel);
    expect(await suggererAdresses(" 8 ")).toEqual([]);
    expect(appel).not.toHaveBeenCalled();
  });

  it("n'envoie que la saisie, vers la Géoplateforme", async () => {
    const appel = reponse([]);
    vi.stubGlobal("fetch", appel);
    await suggererAdresses("12 rue des Érables");
    const url = new URL(appel.mock.calls[0][0]);
    expect(url.origin).toBe("https://data.geopf.fr");
    expect(url.searchParams.get("q")).toBe("12 rue des Érables");
  });

  it("un service en panne ne propose rien, sans erreur", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    expect(await suggererAdresses("8 rue mercière")).toEqual([]);
  });
});

describe("villesDuCodePostal", () => {
  it("écarte les communes voisines et écrit les arrondissements comme La Poste", async () => {
    vi.stubGlobal(
      "fetch",
      reponse([
        { postcode: "69003", city: "Lyon 3e Arrondissement" },
        { postcode: "69001", city: "Lyon 1er Arrondissement" },
      ]),
    );
    expect(await villesDuCodePostal("69003")).toEqual(["Lyon"]);
  });

  it("ignore un code incomplet", async () => {
    const appel = vi.fn();
    vi.stubGlobal("fetch", appel);
    expect(await villesDuCodePostal("6900")).toEqual([]);
    expect(appel).not.toHaveBeenCalled();
  });
});
