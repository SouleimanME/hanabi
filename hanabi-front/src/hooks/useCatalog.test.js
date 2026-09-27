/** Catalogue : affiché tout de suite depuis la dernière visite, puis mis à jour. */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const list = vi.fn();
const featured = vi.fn();
vi.mock("../lib/api.js", () => ({
  Products: { list: (...a) => list(...a), featured: (...a) => featured(...a) },
}));

import { useCatalog } from "./useCatalog.js";

const PARAMS = { category: "Tout", query: "", sort: "pop", lang: "fr" };
const LAMPE = { id: 1, name: "Lampe", art: "https://api.test/media/abc" };
const LANTERNE = { id: 2, name: "Lanterne", art: "https://api.test/media/def" };

beforeEach(() => {
  localStorage.clear();
  list.mockReset();
  featured.mockReset().mockResolvedValue([]);
});
afterEach(() => localStorage.clear());

describe("useCatalog", () => {
  it("première visite : chargement, puis la grille", async () => {
    list.mockResolvedValue([LAMPE]);
    const { result } = renderHook(() => useCatalog(PARAMS));
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.products).toEqual([LAMPE]));
  });

  it("visite suivante : la grille d'avant s'affiche sans attendre le serveur", async () => {
    list.mockResolvedValue([LAMPE]);
    const premiere = renderHook(() => useCatalog(PARAMS));
    await waitFor(() => expect(premiere.result.current.products).toEqual([LAMPE]));
    premiere.unmount();

    // Serveur endormi : la réponse n'arrive pas
    list.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useCatalog(PARAMS));
    expect(result.current.loading).toBe(false);
    expect(result.current.products).toEqual([LAMPE]);
    expect(result.current.refreshing).toBe(false);
  });

  it("la réponse du serveur remplace la grille en cache", async () => {
    localStorage.setItem(
      "hanabi:catalogue:v1",
      JSON.stringify({ "fr|Tout|pop": { le: 1, donnees: [LAMPE] } }),
    );
    list.mockResolvedValue([LAMPE, LANTERNE]);
    const { result } = renderHook(() => useCatalog(PARAMS));
    expect(result.current.products).toEqual([LAMPE]);
    await waitFor(() => expect(result.current.products).toEqual([LAMPE, LANTERNE]));
  });

  it("serveur en panne après une visite : la grille reste, sans message d'erreur", async () => {
    localStorage.setItem(
      "hanabi:catalogue:v1",
      JSON.stringify({ "fr|Tout|pop": { le: 1, donnees: [LAMPE] } }),
    );
    list.mockRejectedValue(new Error("Serveur injoignable"));
    const { result } = renderHook(() => useCatalog(PARAMS));
    await waitFor(() => expect(list).toHaveBeenCalled());
    await waitFor(() => expect(result.current.refreshing).toBe(false));
    expect(result.current.error).toBeNull();
    expect(result.current.products).toEqual([LAMPE]);
  });

  it("une recherche n'est pas gardée", async () => {
    list.mockResolvedValue([LAMPE]);
    const { result } = renderHook(() => useCatalog({ ...PARAMS, query: "lampe" }));
    await waitFor(() => expect(result.current.products).toEqual([LAMPE]));
    const cache = JSON.parse(localStorage.getItem("hanabi:catalogue:v1") || "{}");
    expect(Object.keys(cache).filter((vue) => !vue.startsWith("featured|"))).toEqual([]);
  });

  it("un catalogue aux photos embarquées n'est pas gardé", async () => {
    list.mockResolvedValue([{ ...LAMPE, art: "data:image/jpeg;base64,AAAA" }]);
    const { result } = renderHook(() => useCatalog(PARAMS));
    await waitFor(() => expect(result.current.products).toHaveLength(1));
    const cache = JSON.parse(localStorage.getItem("hanabi:catalogue:v1") || "{}");
    expect(cache["fr|Tout|pop"]).toBeUndefined();
  });
});
