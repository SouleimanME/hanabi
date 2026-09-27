/** Ce que les visiteurs cherchent : besoins, comptes, états vide et dégradé. */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../lib/api.js", () => ({
  API_BASE: "http://api.test",
  getToken: () => "jeton-de-test",
  messageDeValidation: () => "Champ invalide",
}));

import Demandes from "./Demandes.jsx";

const besoin = (nom, demandes, sources = { recherche: demandes }, exemples = []) => ({
  besoin: nom,
  demandes,
  sources,
  exemples,
  derniere: "2026-09-27T10:00:00+00:00",
});

const repondre = (corps) =>
  vi.stubGlobal("fetch", async () => ({ ok: true, status: 200, json: async () => corps }));

afterEach(() => vi.unstubAllGlobals());

describe("Ce que tes visiteurs cherchent", () => {
  it("montre chaque besoin, son compte et d'où il vient", async () => {
    repondre({
      jours: 30,
      total: 6,
      regroupe: true,
      besoins: [
        besoin("Coque de téléphone", 5, { recherche: 3, conseil: 2 }, [
          "coque iphone",
          "phone case",
        ]),
        besoin("Tapis de souris", 1),
      ],
    });
    render(<Demandes />);
    expect(await screen.findByText("Coque de téléphone")).toBeInTheDocument();
    expect(screen.getByText("5 demandes")).toBeInTheDocument();
    expect(screen.getByText("1 demande")).toBeInTheDocument();
    expect(screen.getByText("3 recherches · 2 via le conseiller")).toBeInTheDocument();
    expect(screen.getByText("coque iphone")).toBeInTheDocument();
  });

  it("n'en montre que huit, le reste à la demande", async () => {
    repondre({
      jours: 30,
      total: 10,
      regroupe: true,
      besoins: Array.from({ length: 10 }, (_, i) => besoin(`Besoin ${i + 1}`, 10 - i)),
    });
    const util = userEvent.setup();
    render(<Demandes />);
    await screen.findByText("Besoin 1");
    expect(screen.queryByText("Besoin 9")).not.toBeInTheDocument();
    await util.click(screen.getByRole("button", { name: "Voir les 10 besoins" }));
    expect(screen.getByText("Besoin 10")).toBeInTheDocument();
  });

  it("dit quand tout ce qu'on cherche est en boutique", async () => {
    repondre({ jours: 30, total: 0, regroupe: false, besoins: [] });
    render(<Demandes />);
    expect(await screen.findByText(/la boutique l'a/i)).toBeInTheDocument();
  });

  it("prévient quand le regroupement n'a pas pu se faire", async () => {
    repondre({ jours: 30, total: 1, regroupe: false, besoins: [besoin("coque iphone", 1)] });
    render(<Demandes />);
    expect(await screen.findByText(/regroupement indisponible/i)).toBeInTheDocument();
  });
});
