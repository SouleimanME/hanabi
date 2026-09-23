/** Banque émettrice : table locale, noms que le client reconnaît. */
import { describe, it, expect } from "vitest";

import table from "../content/banques.json";
import { CARTE_DE_TEST, banqueDe, nomDeBanque } from "./banques.js";

const premierBin = (nom) => table[nom].split(" ")[0];

describe("table des banques", () => {
  it("ne contient que des BIN à six chiffres, chacun rangé une seule fois", () => {
    const tous = Object.values(table).flatMap((bins) => bins.split(" "));
    expect(tous.every((bin) => /^\d{6}$/.test(bin))).toBe(true);
    expect(new Set(tous).size).toBe(tous.length);
  });

  it("couvre les grandes banques françaises", () => {
    for (const nom of ["Crédit Agricole", "BNP Paribas", "Société Générale", "La Banque Postale"]) {
      expect(table[nom], nom).toBeTruthy();
    }
  });

  it("ne nomme aucun sous-traitant technique", () => {
    const noms = Object.keys(table).join(" ");
    expect(noms).not.toMatch(/Treezor|Contis|Mastercard France|Natixis/i);
  });
});

describe("banqueDe", () => {
  it("trouve la banque dès le sixième chiffre", async () => {
    const bin = premierBin("Crédit Agricole");
    expect(await banqueDe(`${bin}1234567890`)).toBe("Crédit Agricole");
    expect(await banqueDe(bin.slice(0, 5))).toBeNull();
  });

  it("reconnaît les numéros de test proposés par la boutique", async () => {
    expect(await banqueDe("4242 4242 4242 4242")).toBe(CARTE_DE_TEST);
    expect(await banqueDe("4000 0000 0000 0002")).toBe(CARTE_DE_TEST);
  });

  it("se tait sur une carte qu'elle ne connaît pas", async () => {
    // La carte de la capture d'écran : BIN d'une coopérative américaine
    expect(await banqueDe("4213 7213 8213 9821")).toBeNull();
  });
});

describe("nomDeBanque", () => {
  it("nomme les deux enseignes d'un groupe, dans la langue affichée", () => {
    expect(nomDeBanque("Crédit Mutuel|CIC", "fr")).toBe("Crédit Mutuel ou CIC");
    expect(nomDeBanque("Crédit Mutuel|CIC", "en")).toBe("Crédit Mutuel or CIC");
    expect(nomDeBanque("LCL", "es")).toBe("LCL");
  });
});
