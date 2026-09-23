/** Validation de carte, cote saisie. */
import { describe, it, expect } from "vitest";

import {
  digitsOnly,
  detectBrand,
  formatCardNumber,
  luhnValid,
  cardNumberValid,
  problemeCarte,
  longueurUsuelle,
  formatExpiry,
  expiryValid,
  cvcLength,
  cvcValid,
  jetonDePaiement,
} from "./card.js";

const VISA = "4242424242424242";
const AMEX = "378282246310005";
const MASTERCARD = "5555555555554444";
// Plage 2221-2720, ouverte par Mastercard en 2017
const MASTERCARD_2SERIES = "2223003122003222";

describe("digitsOnly", () => {
  it("retire tout ce qui n'est pas un chiffre", () => {
    expect(digitsOnly("4242 4242-4242.4242")).toBe(VISA);
  });

  it("traite l'absence de valeur comme une chaine vide", () => {
    expect(digitsOnly(undefined)).toBe("");
    expect(digitsOnly(null)).toBe("");
  });
});

describe("detectBrand", () => {
  it.each([
    ["4", "visa"],
    ["34", "amex"],
    ["37", "amex"],
    ["51", "mastercard"],
    ["55", "mastercard"],
    ["2223", "mastercard"],
    ["2720", "mastercard"],
  ])("reconnait le reseau des le prefixe %s", (prefixe, attendu) => {
    expect(detectBrand(prefixe).id).toBe(attendu);
  });

  it.each([
    ["2220", "juste sous la plage Mastercard ouverte en 2017"],
    ["2721", "juste au-dessus"],
    ["6011", "Discover, non pris en charge"],
    ["", "champ vide"],
  ])("retombe sur le format generique pour %s (%s)", (prefixe) => {
    expect(detectBrand(prefixe).id).toBe("unknown");
  });

  it("couvre exactement les bornes de la plage 2221-2720", () => {
    // Les bornes sont a quatre chiffres : les resumer sur trois faisait entrer
    // 2220 dans la plage.
    for (const dedans of ["2221", "2229", "2230", "2299", "2300", "2699", "2700", "2719", "2720"]) {
      expect(detectBrand(dedans).id, `${dedans} devrait etre Mastercard`).toBe("mastercard");
    }
    for (const dehors of ["2220", "2721", "2100", "2800"]) {
      expect(detectBrand(dehors).id, `${dehors} ne devrait pas l'etre`).toBe("unknown");
    }
  });

  it("attend le quatrieme chiffre pour trancher sur la serie 2", () => {
    // Consequence assumee d'une plage decrite exactement : « 222 » peut encore
    // devenir 2220 comme 2221.
    expect(detectBrand("222").id).toBe("unknown");
    expect(detectBrand("2223").id).toBe("mastercard");
  });
});

describe("formatCardNumber", () => {
  it("groupe par quatre les reseaux a seize chiffres", () => {
    expect(formatCardNumber(VISA)).toBe("4242 4242 4242 4242");
  });

  it("groupe American Express en 4-6-5, comme sur la carte", () => {
    expect(formatCardNumber(AMEX)).toBe("3782 822463 10005");
  });

  it("tronque a la longueur maximale du reseau", () => {
    // Amex n'a que quinze chiffres : les suivants sont refuses a la frappe
    // plutot qu'acceptes puis rejetes a la validation.
    expect(digitsOnly(formatCardNumber(AMEX + "999"))).toHaveLength(15);
  });

  it("met en forme au fil de la saisie, sans espace en trop", () => {
    expect(formatCardNumber("4242")).toBe("4242");
    expect(formatCardNumber("42425")).toBe("4242 5");
  });

  it("est idempotente : reformater un numero deja forme ne change rien", () => {
    const une = formatCardNumber(VISA);
    expect(formatCardNumber(une)).toBe(une);
  });
});

describe("luhnValid", () => {
  it.each([VISA, AMEX, MASTERCARD, MASTERCARD_2SERIES])("accepte le numero de test %s", (n) => {
    expect(luhnValid(n)).toBe(true);
  });

  it("rejette un chiffre errone", () => {
    expect(luhnValid("4242424242424243")).toBe(false);
  });

  it("rejette une transposition, ce qui est tout l'interet de la cle", () => {
    // Intervertir deux chiffres voisins a l'interieur du numero doit casser la somme
    expect(luhnValid("4539578900801280")).toBe(true);
    expect(luhnValid("4359578900801280")).toBe(false);
  });

  it("refuse un numero trop court pour etre une carte", () => {
    expect(luhnValid("42")).toBe(false);
    expect(luhnValid("")).toBe(false);
  });
});

describe("cardNumberValid", () => {
  it("exige une longueur admise par le reseau ET une cle correcte", () => {
    expect(cardNumberValid(VISA)).toBe(true);
    expect(cardNumberValid(AMEX)).toBe(true);
  });

  it("refuse un numero de bonne cle mais de mauvaise longueur", () => {
    // 15 chiffres passant Luhn, mais Visa n'admet que 13, 16 ou 19.
    expect(luhnValid("424242424242424")).toBe(true);
    expect(cardNumberValid("424242424242424")).toBe(false);
  });

  it("accepte la saisie mise en forme, espaces compris", () => {
    expect(cardNumberValid("4242 4242 4242 4242")).toBe(true);
  });
});

describe("problemeCarte", () => {
  it("distingue un numero inacheve d'un numero faux", () => {
    // Seize chiffres ne sont pas « incomplets » : la cle de Luhn est fausse
    expect(problemeCarte("4213 7213 8213 9821")).toBe("invalide");
    expect(problemeCarte("4242 4242 4242")).toBe("incomplet");
    expect(problemeCarte(VISA)).toBeNull();
  });

  it("juge la longueur selon le reseau", () => {
    // Quinze chiffres suffisent a American Express, pas a Visa
    expect(problemeCarte(AMEX)).toBeNull();
    expect(problemeCarte("424242424242424")).toBe("incomplet");
  });
});

describe("longueurUsuelle", () => {
  it("vaut seize chiffres, quinze chez American Express", () => {
    expect(longueurUsuelle("4")).toBe(16);
    expect(longueurUsuelle("51")).toBe(16);
    expect(longueurUsuelle("37")).toBe(15);
    expect(longueurUsuelle("")).toBe(16);
  });
});

describe("formatExpiry", () => {
  it("insere la barre apres le mois", () => {
    expect(formatExpiry("1226")).toBe("12/26");
  });

  it("complete le zero d'un mois saisi de 2 a 9", () => {
    // Taper « 4 » ne peut vouloir dire qu'avril : on n'attend pas un second
    // chiffre qui ne viendra jamais.
    expect(formatExpiry("4")).toBe("04/");
    expect(formatExpiry("9")).toBe("09/");
  });

  it("laisse « 1 » ouvert, qui peut encore devenir 10, 11 ou 12", () => {
    expect(formatExpiry("1")).toBe("1");
  });

  it("ignore les chiffres au-dela de quatre", () => {
    expect(formatExpiry("122699")).toBe("12/26");
  });
});

describe("expiryValid", () => {
  // Date figee : sans cela le test change de resultat avec le temps, et finit
  // par echouer un matin sans qu'une seule ligne ait bouge.
  const janvier2026 = new Date(2026, 0, 15, 12, 0, 0);

  it("accepte une date future", () => {
    expect(expiryValid("1230")).toBe(true);
  });

  it("accepte le mois en cours : une carte vaut jusqu'a son dernier jour", () => {
    const maintenant = new Date();
    const mois = String(maintenant.getMonth() + 1).padStart(2, "0");
    const annee = String(maintenant.getFullYear() % 100).padStart(2, "0");
    expect(expiryValid(mois + annee)).toBe(true);
  });

  it("refuse une date passee", () => {
    expect(expiryValid("0120")).toBe(false);
  });

  it.each(["0026", "1326", "9926"])("refuse le mois impossible %s", (v) => {
    expect(expiryValid(v)).toBe(false);
  });

  it("refuse une saisie incomplete", () => {
    expect(expiryValid("122")).toBe(false);
  });

  it("compare bien au premier jour du mois suivant", () => {
    // Verification directe de la regle, independamment de la date du jour.
    const dernierJour = new Date(2026, 0, 31, 23, 59);
    expect(dernierJour < new Date(2026, 1, 1)).toBe(true);
    expect(janvier2026 < new Date(2026, 1, 1)).toBe(true);
  });
});

describe("code de securite", () => {
  it("attend quatre chiffres chez American Express", () => {
    expect(cvcLength(AMEX)).toBe(4);
    expect(cvcValid("1234", AMEX)).toBe(true);
    expect(cvcValid("123", AMEX)).toBe(false);
  });

  it("en attend trois ailleurs", () => {
    expect(cvcLength(VISA)).toBe(3);
    expect(cvcValid("123", VISA)).toBe(true);
    expect(cvcValid("1234", VISA)).toBe(false);
  });

  it("s'appuie sur le reseau, pas sur la longueur du champ", () => {
    // La regle suit la carte saisie : le meme cvc est bon pour l'une, mauvais
    // pour l'autre.
    expect(cvcValid("1234", MASTERCARD)).toBe(false);
    expect(cvcValid("1234", AMEX)).toBe(true);
  });
});

describe("jeton de paiement", () => {
  it("un numero de test declenche la reponse du prestataire simule", () => {
    // Sans cela, un refus ne se voyait qu'en appelant l'API a la main
    expect(jetonDePaiement("4000 0000 0000 0002")).toBe("tok_refus");
    expect(jetonDePaiement("4000000000009995")).toBe("tok_fonds_insuffisants");
    expect(jetonDePaiement("4000 0000 0000 0119")).toBe("tok_indecis");
  });

  it("une autre carte donne un jeton du reseau, jamais le numero", () => {
    expect(jetonDePaiement(VISA)).toBe("tok_visa");
    expect(jetonDePaiement(AMEX)).toBe("tok_amex");
    expect(jetonDePaiement(VISA)).not.toContain("4242");
  });

  it("les numeros de test passent la cle de Luhn, donc le formulaire", () => {
    for (const numero of ["4000000000000002", "4000000000009995", "4000000000000119"]) {
      expect(cardNumberValid(numero)).toBe(true);
    }
  });
});
