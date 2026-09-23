/** Correspondance entre l'etat d'affichage et l'URL. */
import { describe, it, expect } from "vitest";

import { pathFor, parsePath } from "./routes.js";

// Les ecrans a jeton sont exclus de l'aller-retour simple : sans jeton, ils
// retombent volontairement sur l'accueil. Ils ont leur propre section.
const ECRANS = ["home", "wishlist", "saved", "account", "checkout", "done"];
const JETON = "aaaabbbbccccddddeeeeffff";

describe("pathFor", () => {
  it("place l'accueil a la racine", () => {
    expect(pathFor("home")).toBe("/");
  });

  it.each([
    ["wishlist", "/favoris"],
    ["saved", "/enregistres"],
    ["account", "/compte"],
    ["checkout", "/commande"],
    ["done", "/merci"],
  ])("donne a %s le segment stable %s", (vue, chemin) => {
    // Ces chaines sont volontairement figees dans le test : les changer doit
    // demander un geste conscient, puisqu'une URL partagee en depend.
    expect(pathFor(vue)).toBe(chemin);
  });

  it("compose le chemin d'une fiche produit", () => {
    expect(pathFor("product", { id: 42 })).toBe("/produit/42");
  });

  it("retombe sur l'accueil si la fiche est absente", () => {
    expect(pathFor("product", null)).toBe("/");
    expect(pathFor("product", undefined)).toBe("/");
  });

  it("retombe sur l'accueil pour un ecran inconnu", () => {
    expect(pathFor("ecran-qui-n-existe-pas")).toBe("/");
  });
});

describe("parsePath", () => {
  it("lit une fiche produit et son identifiant", () => {
    expect(parsePath("/produit/42")).toEqual({
      view: "product",
      productId: 42,
      jeton: null,
      lien: null,
    });
  });

  it.each([
    ["/produit/abc", "identifiant non numerique"],
    ["/produit/0", "zero"],
    ["/produit/-3", "negatif"],
    ["/produit/1.5", "decimal"],
    ["/produit/", "identifiant absent"],
  ])("renvoie a l'accueil pour %s (%s)", (chemin) => {
    expect(parsePath(chemin)).toEqual({ view: "home", productId: null, jeton: null, lien: null });
  });

  it("renvoie a l'accueil pour une adresse inconnue", () => {
    // Un ancien lien ou une faute de frappe ne doit pas produire d'ecran vide.
    expect(parsePath("/rubrique-supprimee").view).toBe("home");
  });

  it("tolere les barres surnumeraires", () => {
    expect(parsePath("//compte//").view).toBe("account");
    expect(parsePath("/").view).toBe("home");
    expect(parsePath("").view).toBe("home");
  });
});

describe("aller-retour", () => {
  it.each(ECRANS)("%s survit au passage par l'URL", (vue) => {
    expect(parsePath(pathFor(vue)).view).toBe(vue);
  });

  it("une fiche produit conserve son identifiant", () => {
    for (const id of [1, 7, 42, 1000]) {
      expect(parsePath(pathFor("product", { id }))).toEqual({
        view: "product",
        productId: id,
        jeton: null,
        lien: null,
      });
    }
  });

  it("aucun ecran ne partage son segment avec un autre", () => {
    // Deux ecrans sur le meme chemin rendraient l'un des deux inatteignable.
    const chemins = ECRANS.map((v) => pathFor(v));
    expect(new Set(chemins).size).toBe(chemins.length);
  });
});

describe("ecrans atteints depuis un courriel", () => {
  it.each([
    ["verifyEmail", "/confirmer-adresse"],
    ["resetPassword", "/nouveau-mot-de-passe"],
  ])("%s vit a %s", (vue, chemin) => {
    // Ces segments figurent dans des messages deja partis, que personne ne peut
    // corriger. Les renommer casserait tous les liens en circulation.
    expect(pathFor(vue)).toBe(chemin);
  });

  it("lit le jeton dans la requete", () => {
    expect(parsePath("/confirmer-adresse", `?jeton=${JETON}`)).toEqual({
      view: "verifyEmail",
      productId: null,
      jeton: JETON,
      lien: null,
    });
  });

  it("retombe sur l'accueil sans jeton", () => {
    // Adresse tapee a la main, ou lien tronque par un client de messagerie :
    // mieux vaut l'accueil qu'un formulaire qui ne peut rien valider.
    expect(parsePath("/nouveau-mot-de-passe").view).toBe("home");
    expect(parsePath("/nouveau-mot-de-passe", "?autre=1").view).toBe("home");
  });

  it.each([
    ["?jeton=court", "trop court"],
    [`?jeton=${"x".repeat(200)}`, "demesure"],
    ["?jeton=avec%20espace", "caractere interdit"],
    ["?jeton=", "vide"],
  ])("refuse un jeton malforme (%s : %s)", (requete) => {
    expect(parsePath("/confirmer-adresse", requete).view).toBe("home");
  });

  it("accepte le base64url emis par le serveur", () => {
    // 32 octets en base64url font 43 caracteres, tirets et tirets bas compris.
    const emis = "aA1-bB2_cC3-dD4_eE5-fF6_gG7-hH8_iI9-jJ0abc";
    expect(parsePath("/confirmer-adresse", `?jeton=${emis}`).jeton).toBe(emis);
  });

  it("ne remet jamais le jeton dans le chemin", () => {
    // `pathFor` ne produit pas de requete : quitter l'ecran efface le jeton de
    // la barre d'adresse, de l'historique et des signets.
    expect(pathFor("resetPassword")).not.toMatch(/jeton/);
  });
});

describe("lien de desinscription", () => {
  const SIGNATURE = "ab".repeat(32);

  it("vit a /desinscription, segment ecrit dans chaque lettre deja partie", () => {
    expect(pathFor("unsubscribe")).toBe("/desinscription");
  });

  it("lit le numero et la signature", () => {
    expect(parsePath("/desinscription", `?i=42&s=${SIGNATURE}`)).toEqual({
      view: "unsubscribe",
      productId: null,
      jeton: null,
      lien: { id: 42, signature: SIGNATURE },
    });
  });

  it.each([
    ["?s=" + "ab".repeat(32), "numero absent"],
    ["?i=0&s=" + "ab".repeat(32), "numero nul"],
    ["?i=4&s=court", "signature tronquee par la messagerie"],
    ["?i=4&s=" + "zz".repeat(32), "signature hors hexadecimal"],
  ])("retombe sur l'accueil (%s : %s)", (requete) => {
    expect(parsePath("/desinscription", requete).view).toBe("home");
  });
});
