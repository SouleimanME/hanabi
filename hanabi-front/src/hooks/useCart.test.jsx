/** Panier persistant.
 *
 * Le hook est teste directement plutot qu'a travers un composant : ce qui est
 * en jeu ici est une regle de gestion - le plafonnement au stock, l'oubli d'un
 * produit disparu - et non un rendu. Passer par l'interface ajouterait des
 * clics entre le test et ce qu'il verifie.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useCart, ADD_RESULT } from "./useCart.js";
import { storage } from "../lib/storage.js";

const CATALOGUE = {
  1: { id: 1, name: "Lampe Torii", price_cents: 6400, stock: 3 },
  2: { id: 2, name: "Éventail Sensu", price_cents: 2800, stock: 10 },
  3: { id: 3, name: "Kitsune", price_cents: 4800, stock: 0 },
};

const monter = (catalogue = CATALOGUE) => renderHook(() => useCart(catalogue));

beforeEach(() => window.localStorage.clear());

describe("ajout", () => {
  it("ajoute un produit disponible", () => {
    const { result } = monter();
    act(() => expect(result.current.add(1)).toBe(ADD_RESULT.ADDED));
    expect(result.current.count).toBe(1);
    expect(result.current.subtotalCents).toBe(6400);
  });

  it("cumule les ajouts d'un meme produit sur une seule ligne", () => {
    const { result } = monter();
    act(() => result.current.add(2));
    act(() => result.current.add(2, 2));
    expect(result.current.lines).toHaveLength(1);
    expect(result.current.count).toBe(3);
  });

  it("refuse un produit en rupture", () => {
    const { result } = monter();
    act(() => expect(result.current.add(3)).toBe(ADD_RESULT.UNAVAILABLE));
    expect(result.current.count).toBe(0);
  });

  it("refuse un produit absent du catalogue", () => {
    const { result } = monter();
    act(() => expect(result.current.add(999)).toBe(ADD_RESULT.UNAVAILABLE));
  });

  it("plafonne au stock disponible", () => {
    const { result } = monter();
    act(() => expect(result.current.add(1, 10)).toBe(ADD_RESULT.ADDED));
    expect(result.current.count).toBe(3);
  });

  it("signale MAX_STOCK quand le plafond est deja atteint", () => {
    // La distinction compte pour l'interface : « ajoute » et « impossible d'en
    // ajouter plus » n'appellent pas le meme message.
    const { result } = monter();
    act(() => result.current.add(1, 3));
    act(() => expect(result.current.add(1)).toBe(ADD_RESULT.MAX_STOCK));
    expect(result.current.count).toBe(3);
  });
});

describe("quantite", () => {
  it("fixe une quantite", () => {
    const { result } = monter();
    act(() => result.current.add(2));
    act(() => result.current.setQty(2, 5));
    expect(result.current.count).toBe(5);
  });

  it("ne descend jamais sous un : retirer se fait par la corbeille", () => {
    const { result } = monter();
    act(() => result.current.add(2));
    act(() => result.current.setQty(2, 0));
    act(() => result.current.setQty(2, -4));
    expect(result.current.count).toBe(1);
  });

  it("plafonne au stock", () => {
    const { result } = monter();
    act(() => result.current.add(1));
    act(() => result.current.setQty(1, 99));
    expect(result.current.count).toBe(3);
  });
});

describe("suppression", () => {
  it("retire une ligne", () => {
    const { result } = monter();
    act(() => result.current.add(1));
    act(() => result.current.add(2));
    act(() => result.current.remove(1));
    expect(result.current.lines.map((l) => l.id)).toEqual([2]);
  });

  it("vide le panier", () => {
    const { result } = monter();
    act(() => result.current.add(1));
    act(() => result.current.clear());
    expect(result.current.count).toBe(0);
    expect(result.current.subtotalCents).toBe(0);
  });
});

describe("montants", () => {
  it("additionne prix unitaire fois quantite", () => {
    const { result } = monter();
    act(() => result.current.add(1, 2)); // 2 x 64,00
    act(() => result.current.add(2, 3)); // 3 x 28,00
    expect(result.current.subtotalCents).toBe(2 * 6400 + 3 * 2800);
  });

  it("compte en centimes de bout en bout", () => {
    // Aucun flottant : 0,1 + 0,2 ne vaut pas 0,3, et un panier qui affiche
    // 90,00000000000001 euros a perdu la confiance du visiteur.
    const { result } = monter();
    act(() => result.current.add(2, 3));
    expect(Number.isInteger(result.current.subtotalCents)).toBe(true);
  });
});

describe("persistance", () => {
  it("survit au remontage", () => {
    const premier = monter();
    act(() => premier.result.current.add(1, 2));
    premier.unmount();

    const second = monter();
    expect(second.result.current.count).toBe(2);
  });

  it("ne stocke que l'identifiant et la quantite", () => {
    // Le prix relu depuis le catalogue a chaque rendu : un tarif modifie en base
    // s'applique immediatement au lieu de rester fige dans le navigateur.
    const { result } = monter();
    act(() => result.current.add(1));
    expect(storage.get("cart", null)).toEqual([{ id: 1, qty: 1 }]);
  });

  it("repercute un changement de prix survenu en base", () => {
    const premier = monter();
    act(() => premier.result.current.add(1));
    premier.unmount();

    const renchéri = { ...CATALOGUE, 1: { ...CATALOGUE[1], price_cents: 9900 } };
    expect(monter(renchéri).result.current.subtotalCents).toBe(9900);
  });

  it("ignore une ligne dont le produit a disparu du catalogue", () => {
    const premier = monter();
    act(() => premier.result.current.add(1));
    act(() => premier.result.current.add(2));
    premier.unmount();

    // Le produit 1 est retire du catalogue entre deux visites.
    const { result } = monter({ 2: CATALOGUE[2] });
    expect(result.current.lines).toHaveLength(1);
    expect(result.current.count).toBe(1);
    expect(result.current.subtotalCents).toBe(2800);
  });

  it("resiste a un stockage corrompu", () => {
    // Un `localStorage` edite a la main, ou ecrit par une version anterieure, ne
    // doit pas empecher la boutique de s'ouvrir.
    window.localStorage.setItem("hanabi:cart", "{ceci n'est pas du JSON");
    expect(() => monter()).not.toThrow();
    expect(monter().result.current.count).toBe(0);
  });
});

describe("toPayload", () => {
  it("rend le format attendu par l'API", () => {
    const { result } = monter();
    act(() => result.current.add(1, 2));
    expect(result.current.toPayload()).toEqual([{ product_id: 1, qty: 2 }]);
  });
});
