/** Entrepôt : « Demander à l'entrepôt » et son passage vers la console. */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Warehouse } from "./Warehouse.jsx";

vi.mock("../../lib/api.js", () => ({
  API_BASE: "http://api.test",
  getToken: () => "jeton-de-test",
  messageDeValidation: () => "Champ invalide",
}));

const SQL = "select segment, part_ca from gold.gold_segments_rfm order by part_ca desc limit 1";

const REPONSE = {
  question: "Quel segment pèse le plus ?",
  sql: SQL,
  explication: "Le segment dont la part du chiffre d'affaires est la plus grande.",
  refus: null,
  erreur: null,
  tentatives: 1,
  restant: 149,
  resultat: {
    sql: SQL,
    colonnes: [
      { nom: "segment", libelle: "Segment", format: "texte" },
      { nom: "part_ca", libelle: "Part CA", format: "pourcent" },
    ],
    lignes: [["Champions", 0.41]],
    total: 1,
    limite: 50,
    tronque: false,
    tables_lues: ["gold.gold_segments_rfm"],
  },
};

let routes;

beforeEach(() => {
  routes = {
    "GET /admin/warehouse": {
      disponible: true,
      construit_le: new Date().toISOString(),
      couches: [],
      controles: [],
      marts: [
        {
          cle: "segments_rfm",
          titre: "Segments RFM",
          question: "Qui achète ?",
          disponible: true,
          lignes: 7,
        },
      ],
    },
    "GET /admin/warehouse/sql/aide": {
      questions: true,
      schemas: ["gold"],
      delai_max_s: 5,
      limite_max: 500,
      regles: [],
      exemples: [],
    },
    "POST /admin/warehouse/question": REPONSE,
  };
  vi.stubGlobal("fetch", async (url, opts = {}) => {
    const chemin = String(url).replace("http://api.test", "").split("?")[0];
    const cle = `${opts.method || "GET"} ${chemin}`;
    let corps = routes[cle];
    if (cle.startsWith("GET /admin/warehouse/marts/")) {
      corps = {
        cle: "segments_rfm",
        table: "gold_segments_rfm",
        sql: "select * from gold.gold_segments_rfm",
        colonnes: [],
        lignes: [],
        total: 0,
      };
    }
    return {
      ok: corps !== undefined,
      status: corps !== undefined ? 200 : 404,
      json: async () => corps ?? { detail: "Route non simulée" },
    };
  });
});

afterEach(() => vi.unstubAllGlobals());

const poser = async (util, question = "Quel segment pèse le plus ?") => {
  await util.type(await screen.findByLabelText(/question sur l'activité/i), question);
  await util.click(screen.getByRole("button", { name: "Demander" }));
};

describe("Demander à l'entrepôt", () => {
  it("n'apparaît pas quand le serveur n'a pas de fournisseur", async () => {
    routes["GET /admin/warehouse/sql/aide"].questions = false;
    render(<Warehouse flash={vi.fn()} />);
    await screen.findByLabelText("Requête SQL");
    expect(screen.queryByLabelText(/question sur l'activité/i)).not.toBeInTheDocument();
  });

  it("montre l'explication, le résultat et le SQL exécuté", async () => {
    const util = userEvent.setup();
    render(<Warehouse flash={vi.fn()} />);
    await poser(util);
    expect(
      await screen.findByText(/la part du chiffre d'affaires est la plus grande/i),
    ).toBeInTheDocument();
    const reponse = screen.getByRole("table", { name: "Quel segment pèse le plus ?" });
    expect(within(reponse).getByText("Champions")).toBeInTheDocument();
    expect(screen.getByText("Voir le SQL")).toBeInTheDocument();
    expect(screen.getByText(/questions restantes aujourd'hui : 149/i)).toBeInTheDocument();
  });

  it("reprend la requête dans la console", async () => {
    const util = userEvent.setup();
    render(<Warehouse flash={vi.fn()} />);
    await poser(util);
    await util.click(await screen.findByRole("button", { name: "Ouvrir dans la console" }));
    expect(screen.getByLabelText("Requête SQL")).toHaveValue(SQL);
  });

  it("dit pourquoi il refuse, sans rien exécuter", async () => {
    routes["POST /admin/warehouse/question"] = {
      ...REPONSE,
      sql: null,
      explication: null,
      resultat: null,
      refus: "Les adresses e-mail ne sont pas dans l'entrepôt.",
    };
    const util = userEvent.setup();
    render(<Warehouse flash={vi.fn()} />);
    await poser(util, "Les e-mails des clients Champions");
    expect(
      await screen.findByText("Les adresses e-mail ne sont pas dans l'entrepôt."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Voir le SQL")).not.toBeInTheDocument();
  });

  it("une question vide est refusée sans appel", async () => {
    const util = userEvent.setup();
    render(<Warehouse flash={vi.fn()} />);
    await util.click(await screen.findByRole("button", { name: "Demander" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/quelques mots/i);
  });
});
