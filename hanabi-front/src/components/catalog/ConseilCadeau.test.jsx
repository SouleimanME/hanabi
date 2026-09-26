/** Conseil cadeau : absent sans fournisseur, prudent avec la demande, clair sur ses refus. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ConseilCadeau } from "./ConseilCadeau.jsx";
import { I18nProvider } from "../../i18n/context.jsx";
import { translator } from "../../i18n/index.js";

const api = vi.hoisted(() => ({ etat: vi.fn(), demander: vi.fn() }));

vi.mock("../../lib/api.js", () => ({ Conseil: api }));
vi.mock("../../hooks/useAntiBot.js", () => ({
  useAntiBot: () => ({
    getProof: async () => ({ nonce: "1" }),
    honeypotProps: { name: "website" },
  }),
}));

const KITSUNE = {
  id: 7,
  code: "HNB-052",
  name: "Figurine Kitsune",
  price_cents: 4800,
  stock: 4,
  art: "kitsune,#E0452A,#0A0605",
};

const monter = (props = {}) =>
  render(
    <I18nProvider t={translator("fr")}>
      <ConseilCadeau
        lang="fr"
        onOpen={vi.fn()}
        onAdd={vi.fn()}
        eur={(c) => `${(c / 100).toFixed(2)} €`}
        {...props}
      />
    </I18nProvider>,
  );

beforeEach(() => {
  api.etat.mockReset().mockResolvedValue({ actif: true });
  api.demander.mockReset();
});

describe("Conseil cadeau", () => {
  it("n'apparaît pas quand le serveur n'a pas de fournisseur", async () => {
    api.etat.mockResolvedValue({ actif: false });
    const { container } = monter();
    await vi.waitFor(() => expect(api.etat).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("un exemple remplit la demande sans l'envoyer", async () => {
    const util = userEvent.setup();
    monter();
    await util.click(await screen.findByRole("button", { name: /yokai/ }));
    expect(screen.getByLabelText(/pour qui/i)).toHaveValue(
      "Pour ma sœur qui adore les yokai, 50 € maximum",
    );
    expect(api.demander).not.toHaveBeenCalled();
  });

  it("une demande trop courte est refusée sous le champ, sans appel", async () => {
    const util = userEvent.setup();
    monter();
    await util.click(await screen.findByRole("button", { name: /trouver un cadeau/i }));
    expect(screen.getByLabelText(/pour qui/i)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/quelques mots/i)).toBeInTheDocument();
    expect(api.demander).not.toHaveBeenCalled();
  });

  it("montre les objets choisis, avec leur raison et leur prix", async () => {
    api.demander.mockResolvedValue({
      message: "Une piste pour elle.",
      vide: null,
      choix: [{ produit: KITSUNE, raison: "Un esprit renard, pour une amatrice de yokai." }],
    });
    const onAdd = vi.fn();
    const util = userEvent.setup();
    monter({ onAdd });
    await util.type(await screen.findByLabelText(/pour qui/i), "Pour ma sœur qui aime les yokai");
    await util.click(screen.getByRole("button", { name: /trouver un cadeau/i }));

    expect(await screen.findByText("Une piste pour elle.")).toBeInTheDocument();
    const liste = screen.getByRole("list", { name: /suggestions/i });
    expect(liste).toHaveTextContent("Figurine Kitsune");
    expect(liste).toHaveTextContent("48.00 €");
    expect(api.demander).toHaveBeenCalledWith("Pour ma sœur qui aime les yokai", "fr", {
      nonce: "1",
    });

    await util.click(screen.getByRole("button", { name: /ajouter figurine kitsune/i }));
    expect(onAdd).toHaveBeenCalledWith(7);
  });

  it("dit quand le plafond du jour est atteint", async () => {
    api.demander.mockRejectedValue(Object.assign(new Error("429"), { status: 429 }));
    const util = userEvent.setup();
    monter();
    await util.type(await screen.findByLabelText(/pour qui/i), "Pour mon frère");
    await util.click(screen.getByRole("button", { name: /trouver un cadeau/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/reviens demain/i);
  });

  it("dit quand rien n'est en stock dans le budget", async () => {
    api.demander.mockResolvedValue({ message: "", vide: "budget", choix: [] });
    const util = userEvent.setup();
    monter();
    await util.type(await screen.findByLabelText(/pour qui/i), "Un cadeau à moins de 5 €");
    await util.click(screen.getByRole("button", { name: /trouver un cadeau/i }));
    expect(await screen.findByText(/rien en stock dans ce budget/i)).toBeInTheDocument();
  });
});
