/** Fiche produit du back-office : traductions et assistant de fiche. */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Products } from "./Products.jsx";

vi.mock("../../lib/api.js", () => ({
  API_BASE: "http://api.test",
  getToken: () => "jeton-de-test",
  messageDeValidation: () => "Champ invalide",
}));

const KITSUNE = {
  id: 1,
  code: "HNB-052",
  name: "Kitsune",
  category: "Décoration",
  blurb: "Résine",
  price_cents: 4800,
  stock: 4,
  is_new: false,
  active: true,
  featured: false,
  featured_order: 0,
  art: "https://images.example/kitsune.jpg",
  images: ["https://images.example/kitsune.jpg"],
  usages: "",
  alt: "",
  traductions: { en: { name: "Kitsune", blurb: "", usages: "", alt: "" } },
};

const fiche = (nom) => ({
  name: nom,
  blurb: "Résine peinte main, 18 cm",
  usages: "Esprit renard\nPour une étagère",
  alt: "Renard blanc assis",
});
const PROPOSITION = {
  categorie: "Figurines",
  fr: fiche("Figurine Kitsune"),
  en: fiche("Kitsune Figure"),
  es: fiche("Figura Kitsune"),
  photo_lue: true,
  restant: 39,
};

let routes;
let envoye;

beforeEach(() => {
  envoye = null;
  routes = {
    "GET /admin/redaction/etat": { statut: 200, corps: { actif: true, plafond: 40, restant: 40 } },
    "POST /admin/redaction/fiche": { statut: 200, corps: PROPOSITION },
  };
  vi.stubGlobal("fetch", async (url, opts = {}) => {
    const cle = `${opts.method || "GET"} ${String(url).replace("http://api.test", "")}`;
    if (opts.body) envoye = JSON.parse(opts.body);
    const route = routes[cle] ?? { statut: 404, corps: { detail: "Route non simulée" } };
    return {
      ok: route.statut < 400,
      status: route.statut,
      json: async () => route.corps,
    };
  });
});

afterEach(() => vi.unstubAllGlobals());

const ouvrir = async (util, props = {}) => {
  render(<Products items={[KITSUNE]} flash={vi.fn()} reload={vi.fn()} {...props} />);
  await util.click(screen.getByRole("button", { name: props.readonly ? "Voir" : "Modifier" }));
};

describe("Assistant de fiche", () => {
  it("n'apparaît pas quand le serveur n'en a pas", async () => {
    routes["GET /admin/redaction/etat"].corps = { actif: false, plafond: 0, restant: 0 };
    const util = userEvent.setup();
    await ouvrir(util);
    await screen.findByText(/^traductions$/i);
    expect(screen.queryByRole("button", { name: /proposer la fiche/i })).not.toBeInTheDocument();
  });

  it("remplit la fiche en trois langues, et la version d'avant reste à un clic", async () => {
    const util = userEvent.setup();
    await ouvrir(util);
    await util.type(await screen.findByLabelText(/notes pour l'assistant/i), "renard blanc");
    await util.click(screen.getByRole("button", { name: /proposer la fiche/i }));

    expect(await screen.findByDisplayValue("Figurine Kitsune")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Kitsune Figure")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Figura Kitsune")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/relisez chaque champ/i);
    // Ce qui est parti : les notes et la photo principale
    expect(envoye).toMatchObject({ notes: "renard blanc", image: KITSUNE.images[0] });

    await util.click(screen.getByRole("button", { name: /revenir à ma version/i }));
    expect(screen.getAllByDisplayValue("Kitsune")).toHaveLength(2);
    expect(screen.queryByDisplayValue("Figurine Kitsune")).not.toBeInTheDocument();
  });

  it("dit pourquoi il n'a rien proposé", async () => {
    routes["POST /admin/redaction/fiche"] = {
      statut: 429,
      corps: { detail: "Plafond du jour atteint pour l'assistant : il revient demain." },
    };
    const util = userEvent.setup();
    await ouvrir(util);
    await util.click(await screen.findByRole("button", { name: /proposer la fiche/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/revient demain/i);
  });

  it("s'essaie en démonstration, sans pouvoir enregistrer", async () => {
    const util = userEvent.setup();
    await ouvrir(util, { readonly: true });
    await util.click(await screen.findByRole("button", { name: /proposer la fiche/i }));
    expect(await screen.findByDisplayValue("Figurine Kitsune")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /enregistrer les modifications/i })).toBeDisabled();
  });
});
