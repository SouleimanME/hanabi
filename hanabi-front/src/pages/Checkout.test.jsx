/** Paiement : messages justes, champs qui n'acceptent que ce qu'ils attendent. */
import { afterEach, beforeAll, beforeEach, describe, it, expect, vi } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Checkout } from "./Checkout.jsx";
import { I18nProvider } from "../i18n/context.jsx";
import { translator } from "../i18n/index.js";
import { chargerBanques } from "../lib/banques.js";

const DISP = { subtotal_cents: 8800, discount_cents: 0, shipping_cents: 0, total_cents: 8800 };

function monter() {
  render(
    <I18nProvider t={translator("fr")}>
      <Checkout
        lines={[]}
        disp={DISP}
        onApplyPromo={vi.fn()}
        onClearPromo={vi.fn()}
        onBack={vi.fn()}
        onPay={vi.fn()}
        lang="fr"
        eur={(c) => `${(c / 100).toFixed(2)} €`}
      />
    </I18nProvider>,
  );
}

const saisir = (libelle, valeur) =>
  fireEvent.change(screen.getByLabelText(libelle), { target: { value: valeur } });

// La banque (dès le sixième chiffre) et les communes (au cinquième chiffre du code
// postal) se cherchent en tâche de fond : on les laisse répondre avant la fin du test
beforeAll(() => chargerBanques());
const laisserFinir = () => act(() => new Promise((r) => setTimeout(r, 0)));

// Aucune commune ni adresse : le test ne sort pas sur le réseau
beforeEach(() =>
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({ features: [] }) }),
  ),
);
afterEach(() => vi.unstubAllGlobals());

describe("numéro de carte", () => {
  it("seize chiffres à la clé fausse sont invalides, pas incomplets", async () => {
    monter();
    saisir("Numéro de carte", "4213 7213 8213 9821");
    expect(screen.getByText("Numéro invalide : un chiffre est sans doute erroné.")).toBeVisible();
    expect(screen.queryByText("Numéro de carte incomplet.")).toBeNull();
    await laisserFinir();
  });

  it("un numéro inachevé ne dit rien avant la sortie du champ", async () => {
    monter();
    saisir("Numéro de carte", "4242 4242");
    expect(screen.queryByText(/Numéro/, { selector: ".field-error" })).toBeNull();
    fireEvent.blur(screen.getByLabelText("Numéro de carte"));
    expect(screen.getByText("Numéro de carte incomplet.")).toBeVisible();
    await laisserFinir();
  });

  it("un bon numéro passe la main à l'expiration, puis au cryptogramme", async () => {
    monter();
    saisir("Numéro de carte", "4242424242424242");
    expect(document.activeElement).toBe(screen.getByLabelText("Expiration"));
    saisir("Expiration", "1230");
    expect(document.activeElement).toBe(screen.getByLabelText("Cryptogramme"));
    await laisserFinir();
  });

  it("tapé chiffre à chiffre, un bon numéro n'est jamais « incomplet »", async () => {
    // Le passage au champ suivant se faisait avant l'enregistrement du seizième
    // chiffre : la sortie du champ jugeait alors l'ancien numéro, à quinze chiffres
    const personne = userEvent.setup();
    monter();
    await personne.click(screen.getByLabelText("Numéro de carte"));
    await personne.keyboard("5555555555554444");
    expect(document.activeElement).toBe(screen.getByLabelText("Expiration"));
    await personne.keyboard("1230");
    expect(document.activeElement).toBe(screen.getByLabelText("Cryptogramme"));
    expect(document.querySelectorAll(".field-error")).toHaveLength(0);
    expect(screen.getByLabelText("Numéro de carte")).not.toHaveAttribute("aria-invalid");
    expect(screen.getByLabelText("Expiration")).not.toHaveAttribute("aria-invalid");
    expect(await screen.findByText("Carte de test")).toBeVisible();
  });

  it("montre le logo du réseau reconnu et la banque, quand la table la connaît", async () => {
    monter();
    saisir("Numéro de carte", "4242 4242 4242 4242");
    expect(await screen.findByText("Carte de test")).toBeVisible();
    const logos = document.querySelectorAll(".card-logos img");
    expect([...logos].map((l) => l.getAttribute("src"))).toEqual(["/cartes/visa.svg"]);
    expect(screen.getByLabelText("Numéro de carte")).toHaveAccessibleDescription(
      "Visa. Carte de test",
    );
  });

  it("tant que le réseau est inconnu, les trois cartes acceptées s'affichent", () => {
    monter();
    expect(document.querySelectorAll(".card-logos img")).toHaveLength(3);
  });
});

describe("code postal", () => {
  it("n'accepte que cinq chiffres", async () => {
    monter();
    saisir("Code postal", "75a0112");
    expect(screen.getByLabelText("Code postal")).toHaveValue("75011");
    await laisserFinir();
  });

  it("un code collé avec espace ou lettres garde ses cinq chiffres", async () => {
    // Une longueur maximale sur le champ tronquait « F-69 003 » avant le filtre
    monter();
    expect(screen.getByLabelText("Code postal")).not.toHaveAttribute("maxlength");
    saisir("Code postal", "F-69 003");
    expect(screen.getByLabelText("Code postal")).toHaveValue("69003");
    await laisserFinir();
  });

  it("un code incomplet est signalé en sortant du champ", () => {
    monter();
    saisir("Code postal", "7501");
    fireEvent.blur(screen.getByLabelText("Code postal"));
    expect(screen.getByText("Code postal à cinq chiffres.")).toBeVisible();
  });
});
