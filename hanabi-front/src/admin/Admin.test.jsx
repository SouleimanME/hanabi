/** Back-office : assemblage, navigation, et l'écran d'exploitation.
 *
 * TESTE PAR LE HAUT, en rendant `<Admin />` entier plutôt que ses morceaux. Ce
 * fichier n'exporte qu'un composant racine — les sous-composants sont internes,
 * et les extraire pour les tester changerait le code pour satisfaire le test.
 * Ce qu'on vérifie ici est justement le CÂBLAGE : que l'onglet mène à la bonne
 * vue, que la vue appelle la bonne route, que la réponse arrive à l'écran.
 *
 * `fetch` est remplacé par une table d'itinéraires. Le reste — état, rendu,
 * navigation — est le vrai code.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import Admin from "./Admin.jsx";

vi.mock("../lib/api.js", () => ({
  API_BASE: "http://api.test",
  getToken: () => "jeton-de-test",
}));

/** Réponses par défaut : de quoi monter le back-office sans erreur. */
const DEFAUTS = {
  "/admin/whoami": { email: "patron@test.fr", readonly: false },
  /* Forme RELEVEE sur l'API, pas devinee : `curl /admin/stats` puis valeurs
   * remplacees par des zeros. Une forme inventee a la main diverge des la
   * premiere evolution du point d'entree, et l'echec qu'elle produit -
   * « Cannot read properties of undefined » au milieu du rendu - ne dit jamais
   * qu'il vient du jeu de donnees du test. */
  "/admin/stats": {
    revenue_cents: 0,
    order_count: 0,
    user_count: 0,
    product_count: 0,
    low_stock_count: 0,
    pending_alerts: 0,
    recent_orders: [],
    demographics: {
      civility: { M: 0, F: 0, N: 0, "?": 0 },
      age_buckets: { "<18": 0, "18-24": 0, "25-34": 0, "35-44": 0, "45-54": 0, "55+": 0, "?": 0 },
      top_cities: [],
    },
  },
  "/admin/exploitation": {
    courriels: {
      en_attente: 0,
      envoyes: 12,
      abandonnes: 0,
      attente_la_plus_ancienne: null,
      age_attente_minutes: null,
      seuil_inquietant: 20,
      tentatives_max: 5,
      sortie: "fichier",
      echecs: [],
    },
    commandes_en_attente: [],
  },
};

let itineraires;

/** Remplace une réponse pour un test donné. */
const repondre = (chemin, corps) => {
  itineraires[chemin] = corps;
};

beforeEach(() => {
  itineraires = structuredClone(DEFAUTS);

  vi.stubGlobal("fetch", async (url) => {
    const chemin = String(url).replace("http://api.test", "").split("?")[0];
    const corps = itineraires[chemin];
    return {
      ok: corps !== undefined,
      status: corps !== undefined ? 200 : 404,
      json: async () => (corps !== undefined ? corps : { detail: "Route non simulée" }),
    };
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

const ouvrirOnglet = async (util, nom) => {
  await util.click(screen.getByRole("button", { name: new RegExp(`^${nom}$`, "i") }));
};

describe("Navigation", () => {
  it("affiche les deux groupes du menu", async () => {
    render(<Admin />);

    // « Piloter » et « Gérer » ne sont pas décoratifs : consulter et modifier ne
    // sont pas la même activité, et six entrées indifférenciées coûtent plus à
    // l'œil qu'un intitulé de section.
    expect(await screen.findByText(/^piloter$/i)).toBeInTheDocument();
    expect(screen.getByText(/^gérer$/i)).toBeInTheDocument();
  });

  it("expose toutes les entrées attendues", async () => {
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    for (const entree of [
      "Tableau de bord",
      "Analytique",
      "Entrepôt",
      "Exploitation",
      "Produits",
      "Codes promo",
      "Commandes",
      "Clients",
    ]) {
      expect(screen.getByRole("button", { name: new RegExp(`^${entree}$`) })).toBeInTheDocument();
    }
  });

  it("marque l'onglet actif pour un lecteur d'écran", async () => {
    const util = userEvent.setup();
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    await ouvrirOnglet(util, "Exploitation");

    // `aria-current` et non une simple classe : un contour vermillon ne dit
    // rien à qui n'y voit pas.
    expect(screen.getByRole("button", { name: /^exploitation$/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});

describe("Exploitation", () => {
  it("affiche l'état de la file", async () => {
    const util = userEvent.setup();
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    await ouvrirOnglet(util, "Exploitation");

    expect(await screen.findByText(/^en attente$/i)).toBeInTheDocument();
    expect(screen.getByText(/^abandonnés$/i)).toBeInTheDocument();
    // La sortie configurée : un relais mal réglé se diagnostique d'abord en
    // regardant lequel est actif. On vise la CARTE, pas le mot : « fichier »
    // apparaît aussi dans la note explicative juste en dessous, et un sélecteur
    // qui attrape les deux échoue sur une ambiguïté qui n'en est pas une.
    expect(document.querySelector(".expl-valeur.texte")).toHaveTextContent("fichier");
  });

  it("alerte quand la file n'avance plus", async () => {
    /* L'ÂGE PRIME SUR LE NOMBRE. Vingt messages en attente depuis dix secondes
     * est un fonctionnement normal ; un seul depuis deux heures est une panne,
     * et le compte seul ne distingue pas les deux. */
    const util = userEvent.setup();
    repondre("/admin/exploitation", {
      ...DEFAUTS["/admin/exploitation"],
      courriels: {
        ...DEFAUTS["/admin/exploitation"].courriels,
        en_attente: 1,
        age_attente_minutes: 120,
      },
    });
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    await ouvrirOnglet(util, "Exploitation");

    expect(await screen.findByText(/la file n'avance plus/i)).toBeInTheDocument();
  });

  it("ne crie pas pour une file qui avance", async () => {
    const util = userEvent.setup();
    repondre("/admin/exploitation", {
      ...DEFAUTS["/admin/exploitation"],
      courriels: {
        ...DEFAUTS["/admin/exploitation"].courriels,
        en_attente: 8,
        age_attente_minutes: 2,
      },
    });
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    await ouvrirOnglet(util, "Exploitation");

    await screen.findByText(/^en attente$/i);
    expect(screen.queryByText(/la file n'avance plus/i)).not.toBeInTheDocument();
  });

  it("liste les échecs avec leur motif", async () => {
    const util = userEvent.setup();
    repondre("/admin/exploitation", {
      ...DEFAUTS["/admin/exploitation"],
      courriels: {
        ...DEFAUTS["/admin/exploitation"].courriels,
        abandonnes: 1,
        echecs: [
          {
            id: 1,
            destinataire: "m***d@exemple.fr",
            sujet: "Commande ATL774213 confirmée",
            statut: "abandonne",
            tentatives: 5,
            erreur: "SMTPAuthenticationError: 535 authentification refusée",
            prochaine_tentative: null,
          },
        ],
      },
      commandes_en_attente: [],
    });
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    await ouvrirOnglet(util, "Exploitation");

    expect(await screen.findByText(/SMTPAuthenticationError/)).toBeInTheDocument();
    // L'adresse arrive DÉJÀ masquée du serveur : cet écran diagnostique un
    // relais, il ne lit pas la clientèle.
    expect(screen.getByText("m***d@exemple.fr")).toBeInTheDocument();
  });

  it("annonce les commandes à rapprocher", async () => {
    const util = userEvent.setup();
    repondre("/admin/exploitation", {
      ...DEFAUTS["/admin/exploitation"],
      commandes_en_attente: [
        { numero: "ATL123456", total_cents: 4900, cree_le: null, age_heures: 3.2 },
      ],
    });
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    await ouvrirOnglet(util, "Exploitation");

    expect(await screen.findByText("ATL123456")).toBeInTheDocument();
    expect(screen.getByText(/3.2 h/)).toBeInTheDocument();
  });

  it("dit clairement qu'il n'y a rien à signaler", async () => {
    // Un écran de surveillance vide doit affirmer que tout va bien, pas rester
    // muet : le silence se lit comme un chargement qui n'a pas abouti.
    const util = userEvent.setup();
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    await ouvrirOnglet(util, "Exploitation");

    expect(await screen.findByText(/aucun échec/i)).toBeInTheDocument();
    expect(screen.getByText(/tous les paiements ont été tranchés/i)).toBeInTheDocument();
  });
});

describe("Compte de démonstration", () => {
  it("annonce la lecture seule quand le serveur la déclare", async () => {
    repondre("/admin/whoami", { email: "hanabi@atelier.fr", readonly: true });
    render(<Admin />);

    expect(await screen.findByText(/modifications sont désactivées/i)).toBeInTheDocument();
  });

  it("ne l'annonce pas à un administrateur en écriture", async () => {
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    expect(screen.queryByText(/modifications sont désactivées/i)).not.toBeInTheDocument();
  });
});

describe("Thème du back-office", () => {
  it("est mémorisé, indépendamment de celui de la boutique", async () => {
    const util = userEvent.setup();
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    const bascule = screen.getByRole("button", { name: /sombre|clair/i });
    await util.click(bascule);

    // Clé distincte de `hanabi:theme` : on ne travaille pas huit heures dans la
    // même lumière qu'on parcourt un catalogue.
    expect(window.localStorage.getItem("hanabi:admin-theme")).toBeTruthy();
  });
});

describe("Panne de l'API", () => {
  it("n'affiche pas un écran vide quand une route échoue", async () => {
    const util = userEvent.setup();
    delete itineraires["/admin/exploitation"];
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    await ouvrirOnglet(util, "Exploitation");

    // Le message du serveur, pas une page blanche : sans lui, on ne saurait pas
    // distinguer « rien à afficher » de « rien n'a répondu ».
    const contenu = await screen.findByText(/non simulée|erreur/i);
    expect(contenu).toBeInTheDocument();
  });
});

describe("Structure", () => {
  it("place le contenu dans un repère de navigation nommé", async () => {
    render(<Admin />);
    await screen.findByText(/^piloter$/i);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("button", { name: /^exploitation$/i })).toBeInTheDocument();
  });
});
