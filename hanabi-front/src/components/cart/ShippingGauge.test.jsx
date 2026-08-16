/** Jauge de livraison offerte.
 *
 * Teste a travers le DOM, contrairement au reste : ce composant n'expose aucune
 * fonction, sa sortie EST son rendu. Ce qu'on verifie est ce qu'un visiteur
 * percoit - la phrase affichee, le montant restant, l'etat de la barre - et non
 * la forme interne du calcul.
 *
 * Les assertions passent par les roles d'accessibilite (`progressbar`) plutot
 * que par les classes CSS. Une classe renommee casserait alors le test sans
 * qu'aucun comportement ait change ; un role disparu, lui, est bien une
 * regression, puisqu'il est ce qu'un lecteur d'ecran annonce.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { ShippingGauge } from "./ShippingGauge.jsx";
import { I18nProvider } from "../../i18n/context.jsx";
import { translator } from "../../i18n/index.js";
import { FREE_SHIPPING_CENTS } from "../../lib/constants.js";

const eur = (cents) => `${(cents / 100).toFixed(2).replace(".", ",")} €`;

const afficher = (props, langue = "fr") =>
  render(
    <I18nProvider t={translator(langue)}>
      <ShippingGauge eur={eur} {...props} />
    </I18nProvider>,
  );

const barre = () => screen.getByRole("progressbar");
const remplissage = () => barre().firstChild;

describe("progression", () => {
  it("part a zero sur un panier vide", () => {
    afficher({ subtotalCents: 0 });
    expect(barre()).toHaveAttribute("aria-valuenow", "0");
    expect(remplissage()).toHaveStyle({ width: "0%" });
  });

  it("rend la moitie du chemin a la moitie du seuil", () => {
    afficher({ subtotalCents: FREE_SHIPPING_CENTS / 2 });
    expect(barre()).toHaveAttribute("aria-valuenow", "50");
    expect(remplissage()).toHaveStyle({ width: "50%" });
  });

  it("ne depasse jamais cent pour cent", () => {
    // Sans plafonnement, un gros panier etirait la barre hors de sa piste.
    afficher({ subtotalCents: FREE_SHIPPING_CENTS * 4 });
    expect(barre()).toHaveAttribute("aria-valuenow", "100");
    expect(remplissage()).toHaveStyle({ width: "100%" });
  });

  it("declare des bornes exploitables par un lecteur d'ecran", () => {
    afficher({ subtotalCents: 1000 });
    expect(barre()).toHaveAttribute("aria-valuemin", "0");
    expect(barre()).toHaveAttribute("aria-valuemax", "100");
    expect(barre()).toHaveAccessibleName();
  });
});

describe("franchissement du seuil", () => {
  it("annonce le montant restant sous le seuil", () => {
    afficher({ subtotalCents: FREE_SHIPPING_CENTS - 1200 });
    expect(screen.getByText(/12,00 €/)).toBeInTheDocument();
  });

  it("bascule exactement AU seuil, pas un centime plus loin", () => {
    // La borne est inclusive cote serveur (`after >= seuil`) : un panier pile a
    // 80,00 € doit annoncer le port offert.
    afficher({ subtotalCents: FREE_SHIPPING_CENTS });
    expect(barre()).toHaveAttribute("aria-valuenow", "100");
    expect(screen.queryByText(/0,00 €/)).not.toBeInTheDocument();
  });

  it("annonce encore un reste a un centime du seuil", () => {
    afficher({ subtotalCents: FREE_SHIPPING_CENTS - 1 });
    expect(screen.getByText(/0,01 €/)).toBeInTheDocument();
  });
});

describe("prise en compte de la remise", () => {
  it("retranche la remise du sous-total", () => {
    // Coherence avec `app/pricing.py`, qui applique le seuil APRES remise. Un
    // code promo qui repasse le panier sous les 80 € doit rendre le port
    // payant, et la jauge doit le dire avant la page de paiement.
    afficher({ subtotalCents: FREE_SHIPPING_CENTS + 1000, discountCents: 2000 });
    expect(barre()).not.toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText(/10,00 €/)).toBeInTheDocument();
  });

  it("ne descend jamais sous zero, meme si la remise excede le panier", () => {
    afficher({ subtotalCents: 1000, discountCents: 9999 });
    expect(barre()).toHaveAttribute("aria-valuenow", "0");
  });

  it("traite une remise absente comme nulle", () => {
    afficher({ subtotalCents: 4000 });
    expect(barre()).toHaveAttribute("aria-valuenow", "50");
  });
});

describe("traduction", () => {
  it("suit la langue affichee", () => {
    const fr = afficher({ subtotalCents: 1000 });
    const texteFr = fr.container.textContent;
    fr.unmount();

    afficher({ subtotalCents: 1000 }, "en");
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(document.body.textContent).not.toBe(texteFr);
  });

  it("n'affiche jamais une cle de traduction brute", () => {
    // Le filet le plus utile de tous : une cle oubliee se voit tout de suite ici.
    for (const langue of ["fr", "en", "es"]) {
      const vue = afficher({ subtotalCents: 1000 }, langue);
      expect(vue.container.textContent).not.toMatch(/^ship[A-Z]/);
      expect(vue.container.textContent).not.toMatch(/\{[a-z]+\}/);
      vue.unmount();
    }
  });
});
