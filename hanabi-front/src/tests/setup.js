/** Amorce commune a tous les tests.
 *
 * Trois choses seulement, parce qu'une amorce qui en fait davantage devient une
 * dependance cachee : chaque test se lit alors avec un contexte qu'il ne montre
 * pas, et un test qui echoue oblige a relire ce fichier avant lui.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  // Demonte l'arbre React et rend le document a son etat initial : sans cela,
  // deux tests rendant le meme composant verraient chacun deux exemplaires, et
  // `getByRole` echouerait sur une ambiguite qui n'existe pas dans l'application.
  cleanup();
  window.localStorage.clear();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// jsdom n'implemente ni ResizeObserver ni matchMedia, que plusieurs composants
// interrogent au montage. Les remplacer ici plutot que dans chaque test evite
// de repeter un bruit de fond qui n'appartient a aucun scenario en particulier.
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
