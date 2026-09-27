/** Fiche produit : déclinaisons (prix, stock, photo de la couleur) et vidéos de la galerie. */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProductPage } from "./ProductPage.jsx";
import { I18nProvider } from "../i18n/context.jsx";
import { translator } from "../i18n/index.js";

vi.mock("../lib/api.js", () => ({
  Products: {
    view: () => Promise.resolve(),
    affinites: () => Promise.resolve([]),
  },
}));
vi.mock("../hooks/useAntiBot.js", () => ({
  useAntiBot: () => ({ getProof: async () => ({}), honeypotProps: { name: "website" } }),
}));

const eur = (c) => `${(c / 100).toFixed(2).replace(".", ",")} €`;
eur.short = eur;

const GOURDE = {
  id: 7,
  code: "HNB-120",
  name: "Gourde isotherme",
  category: "Accessoires",
  blurb: "Inox double paroi",
  price_cents: 1180,
  stock: 2,
  art: "https://images.example/gourde.jpg",
  images: ["https://images.example/gourde.jpg", "https://pub.r2.dev/videos/gourde.mp4"],
  rating_avg: 0,
  rating_count: 0,
  variantes: [
    { id: 71, libelle: "Noir", couleur: "#111111", price_cents: 1180, stock: 0, image: "" },
    {
      id: 72,
      libelle: "Blanc",
      couleur: "#f4f1ea",
      price_cents: 1274,
      stock: 2,
      image: "https://images.example/gourde-blanche.jpg",
    },
  ],
};

const monter = (props = {}) => {
  const onAddItem = vi.fn();
  render(
    <I18nProvider t={translator("fr")}>
      <ProductPage
        p={GOURDE}
        reviews={[]}
        onBack={vi.fn()}
        onAddItem={onAddItem}
        onOpenCart={vi.fn()}
        onOpen={vi.fn()}
        onNotify={vi.fn()}
        onWish={vi.fn()}
        related={[]}
        lang="fr"
        eur={eur}
        {...props}
      />
    </I18nProvider>,
  );
  return { onAddItem };
};

describe("déclinaisons", () => {
  it("part sur la première couleur en stock, à son prix", () => {
    monter();
    expect(screen.getByRole("radio", { name: /Blanc/ })).toBeChecked();
    expect(screen.getAllByText("12,74 €").length).toBeGreaterThan(0);
  });

  it("ajoute la couleur choisie", async () => {
    const util = userEvent.setup();
    const { onAddItem } = monter();
    await util.click(document.querySelector(".buy-add"));
    expect(onAddItem).toHaveBeenCalledWith(7, 1, 72);
  });

  it("une couleur épuisée se dit, sans promettre d'alerte qui ne viendrait pas", async () => {
    const util = userEvent.setup();
    monter();
    await util.click(screen.getByRole("radio", { name: /Noir/ }));
    expect(document.querySelector(".buy-epuise")).toHaveTextContent("Épuisé");
    expect(document.querySelector(".buy-add")).toBeNull();
    expect(screen.queryByPlaceholderText(/adresse/i)).not.toBeInTheDocument();
  });

  it("la photo de la couleur passe en tête de la galerie", () => {
    monter();
    const principale = document.querySelector(".gallery-main img");
    expect(principale.getAttribute("src")).toBe("https://images.example/gourde-blanche.jpg");
  });
});

describe("vidéos", () => {
  it("choisie d'un clic, la vidéo démarre d'elle-même dans le lecteur maison", async () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    const util = userEvent.setup();
    monter();
    await util.click(screen.getByRole("radio", { name: /Vidéo/ }));
    const video = await vi.waitFor(() => {
      const v = document.querySelector(".gallery-main .lecteur video");
      if (!v) throw new Error("lecteur pas encore chargé");
      return v;
    });
    expect(video.getAttribute("src")).toBe("https://pub.r2.dev/videos/gourde.mp4");
    // Le lecteur maison remplace les commandes du navigateur
    expect(video.hasAttribute("controls")).toBe(false);
    expect(play).toHaveBeenCalled();
    expect(screen.getByRole("slider", { name: /position/i })).toBeInTheDocument();
    play.mockRestore();
  });

  it("à part, les vidéos quittent la galerie pour leur propre section", async () => {
    monter({ p: { ...GOURDE, videos_a_part: true } });
    expect(screen.queryByRole("radio", { name: /Vidéo/ })).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "En vidéo" })).toBeInTheDocument();
    await vi.waitFor(() => {
      if (!document.querySelector(".videos-grille .lecteur video")) throw new Error("pas encore");
    });
    // Pas de lecture sans geste de la personne
    expect(document.querySelector(".videos-grille video").hasAttribute("autoplay")).toBe(false);
  });
});
