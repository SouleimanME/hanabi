/** Amorce commune a tous les tests. */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  // Demonte l'arbre React et rend le document a son etat initial
  cleanup();
  window.localStorage.clear();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// jsdom n'implemente ni ResizeObserver ni matchMedia, que plusieurs composants interrogent au montage
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

window.matchMedia ??= (query) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
  dispatchEvent: () => false,
});
