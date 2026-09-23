/** Propositions d'adresse : clavier et souris, sans jamais bloquer la saisie. */
import { afterEach, describe, it, expect, vi } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";

import { ChampAdresse } from "./ChampAdresse.jsx";
import { I18nProvider } from "../../i18n/context.jsx";
import { translator } from "../../i18n/index.js";

const ADRESSES = [
  { id: "a", type: "housenumber", name: "8 Rue Mercière", postcode: "69002", city: "Lyon" },
  { id: "b", type: "housenumber", name: "8 Rue Merlet", postcode: "33000", city: "Bordeaux" },
];

function monter() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ features: ADRESSES.map((properties) => ({ properties })) }),
    }),
  );
  const onChoisir = vi.fn();
  render(
    <I18nProvider t={translator("fr")}>
      <label htmlFor="adr">Adresse</label>
      <ChampAdresse id="adr" value="" onChange={() => {}} onChoisir={onChoisir} />
    </I18nProvider>,
  );
  const champ = screen.getByRole("combobox", { name: "Adresse" });
  champ.focus();
  fireEvent.change(champ, { target: { value: "8 rue mer" } });
  return { champ, onChoisir };
}

afterEach(() => vi.unstubAllGlobals());

describe("ChampAdresse", () => {
  it("propose les adresses après une pause de frappe", async () => {
    const { champ } = monter();
    await waitFor(() => expect(champ).toHaveAttribute("aria-expanded", "true"));
    expect(screen.getAllByRole("option")).toHaveLength(2);
    expect(screen.getByText("2 adresses proposées")).toBeInTheDocument();
  });

  it("les flèches parcourent, Entrée choisit sans envoyer le formulaire", async () => {
    const { champ, onChoisir } = monter();
    await waitFor(() => expect(champ).toHaveAttribute("aria-expanded", "true"));
    fireEvent.keyDown(champ, { key: "ArrowDown" });
    fireEvent.keyDown(champ, { key: "ArrowDown" });
    expect(champ.getAttribute("aria-activedescendant")).toBe(screen.getAllByRole("option")[1].id);
    const entree = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
    // Événement brut : on garde `defaultPrevented` à lire, React doit voir la mise à jour
    act(() => {
      champ.dispatchEvent(entree);
    });
    expect(entree.defaultPrevented).toBe(true);
    expect(onChoisir).toHaveBeenCalledWith(
      expect.objectContaining({ adresse: "8 Rue Merlet", cp: "33000", ville: "Bordeaux" }),
    );
  });

  it("un clic choisit, Échap referme", async () => {
    const { champ, onChoisir } = monter();
    await waitFor(() => expect(champ).toHaveAttribute("aria-expanded", "true"));
    fireEvent.keyDown(champ, { key: "Escape" });
    expect(champ).toHaveAttribute("aria-expanded", "false");
    fireEvent.keyDown(champ, { key: "ArrowDown" });
    fireEvent.click(screen.getAllByRole("option")[0]);
    expect(onChoisir).toHaveBeenCalledWith(expect.objectContaining({ ville: "Lyon" }));
  });

  it("Entrée sans choix laisse le formulaire partir", async () => {
    const { champ } = monter();
    await waitFor(() => expect(champ).toHaveAttribute("aria-expanded", "true"));
    const entree = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
    // Événement brut : on garde `defaultPrevented` à lire, React doit voir la mise à jour
    act(() => {
      champ.dispatchEvent(entree);
    });
    expect(entree.defaultPrevented).toBe(false);
  });
});
