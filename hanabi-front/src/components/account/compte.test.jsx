/** Ecrans de gestion du compte.
 *
 * Ce qui est verifie ici n'est pas la mise en forme mais deux GARANTIES, dont
 * la seconde est de securite :
 *
 *   1. le formulaire de profil n'envoie que ce qui a change - reposter l'objet
 *      entier ecraserait avec des valeurs perimees ce qu'un autre onglet vient
 *      de modifier ;
 *   2. le numero de carte ne quitte JAMAIS la page. C'est ce qui maintient
 *      l'application hors du perimetre PCI-DSS, et c'est exactement le genre de
 *      propriete qu'une refonte casse sans s'en apercevoir.
 *
 * Le client API est remplace : ces tests portent sur ce que les ecrans
 * DECIDENT d'envoyer, pas sur le transport.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { InfosForm } from "./InfosForm.jsx";
import { Paiements } from "./Paiements.jsx";
import { Securite } from "./Securite.jsx";
import { I18nProvider } from "../../i18n/context.jsx";
import { translator } from "../../i18n/index.js";

vi.mock("../../lib/api.js", () => ({
  Compte: {
    majProfil: vi.fn(),
    changerMotDePasse: vi.fn(),
    changerEmail: vi.fn(),
    paiements: vi.fn(),
    ajouterPaiement: vi.fn(),
    paiementParDefaut: vi.fn(),
    supprimerPaiement: vi.fn(),
  },
}));

const { Compte } = await import("../../lib/api.js");

const UTILISATEUR = {
  id: 1,
  name: "Ada Lovelace",
  email: "ada@hanabi.fr",
  civility: "F",
  birthdate: "1815-12-10",
  phone: "0612345678",
  addr: "12 rue des Erables",
  addr_extra: "",
  cp: "75011",
  city: "Paris",
  email_verified: true,
};

const afficher = (ui) => render(<I18nProvider t={translator("fr")}>{ui}</I18nProvider>);

const champ = (libelle) => screen.getByLabelText(new RegExp(libelle, "i"));

beforeEach(() => {
  vi.clearAllMocks();
  Compte.paiements.mockResolvedValue([]);
});

describe("InfosForm", () => {
  it("n'envoie QUE le champ modifie", async () => {
    const util = userEvent.setup();
    Compte.majProfil.mockResolvedValue(UTILISATEUR);
    afficher(<InfosForm user={UTILISATEUR} onEnregistre={vi.fn()} onAnnuler={vi.fn()} />);

    await util.clear(champ("^Ville"));
    await util.type(champ("^Ville"), "Kyoto");
    await util.click(screen.getByRole("button", { name: /enregistrer/i }));

    await waitFor(() => expect(Compte.majProfil).toHaveBeenCalled());
    // L'adresse, le code postal et le telephone ne doivent PAS figurer dans le
    // corps : ils n'ont pas change.
    expect(Compte.majProfil).toHaveBeenCalledWith({ city: "Kyoto" });
  });

  it("n'annonce aucune modification a l'ouverture", () => {
    afficher(<InfosForm user={UTILISATEUR} onEnregistre={vi.fn()} onAnnuler={vi.fn()} />);

    // Regression corrigee : `PhoneField` emettait « +33 » des le montage, si
    // bien que le formulaire se croyait modifie sans que personne n'y touche -
    // et enregistrer ecrasait le vrai numero.
    expect(screen.getByText(/aucune modification/i)).toBeInTheDocument();
  });

  it("affiche les valeurs deja enregistrees", () => {
    // Un formulaire d'edition qui n'affiche pas l'existant l'ecrase en silence.
    afficher(<InfosForm user={UTILISATEUR} onEnregistre={vi.fn()} onAnnuler={vi.fn()} />);

    expect(champ("^Ville")).toHaveValue("Paris");
    expect(champ("Téléphone")).toHaveValue("0612345678");
    expect(champ("^Adresse$")).toHaveValue("12 rue des Erables");
  });

  it("n'appelle pas l'API quand rien n'a change", async () => {
    const util = userEvent.setup();
    const annuler = vi.fn();
    afficher(<InfosForm user={UTILISATEUR} onEnregistre={vi.fn()} onAnnuler={annuler} />);

    await util.click(screen.getByRole("button", { name: /enregistrer/i }));

    expect(Compte.majProfil).not.toHaveBeenCalled();
    expect(annuler).toHaveBeenCalled();
  });

  it("compte les champs modifies", async () => {
    const util = userEvent.setup();
    afficher(<InfosForm user={UTILISATEUR} onEnregistre={vi.fn()} onAnnuler={vi.fn()} />);

    await util.clear(champ("^Ville"));
    await util.clear(champ("Code postal"));

    expect(screen.getByText(/2 champ/i)).toBeInTheDocument();
  });
});

describe("Paiements", () => {
  const CARTE = {
    id: 7,
    reseau: "visa",
    quatre_derniers: "4242",
    exp_mois: 12,
    exp_annee: 2030,
    libelle: "perso",
    defaut: true,
  };

  it("LE NUMERO DE CARTE NE PART JAMAIS", async () => {
    const util = userEvent.setup();
    Compte.ajouterPaiement.mockResolvedValue(CARTE);
    afficher(<Paiements flash={vi.fn()} />);

    await util.click(await screen.findByRole("button", { name: /ajouter une carte/i }));
    await util.type(champ("Numéro de carte"), "4242424242424242");
    await util.type(champ("Expiration"), "1230");
    await util.click(screen.getByRole("button", { name: /^ajouter une carte$/i }));

    await waitFor(() => expect(Compte.ajouterPaiement).toHaveBeenCalled());
    const envoye = Compte.ajouterPaiement.mock.calls[0][0];

    expect(JSON.stringify(envoye)).not.toContain("4242424242424242");
    expect(envoye).toMatchObject({
      reseau: "visa",
      quatre_derniers: "4242",
      exp_mois: 12,
      exp_annee: 2030,
    });
    // Aucun champ de cryptogramme n'existe : il autorise un paiement, il
    // n'enregistre pas une carte.
    expect(Object.keys(envoye)).not.toContain("cvc");
  });

  it("refuse d'envoyer un numero invalide", async () => {
    const util = userEvent.setup();
    afficher(<Paiements flash={vi.fn()} />);

    await util.click(await screen.findByRole("button", { name: /ajouter une carte/i }));
    // Chiffre transpose : la cle de Luhn doit le rejeter.
    await util.type(champ("Numéro de carte"), "4242424242424243");
    await util.type(champ("Expiration"), "1230");
    await util.click(screen.getByRole("button", { name: /^ajouter une carte$/i }));

    expect(Compte.ajouterPaiement).not.toHaveBeenCalled();
  });

  it("affiche une carte enregistree sans jamais montrer de numero complet", async () => {
    Compte.paiements.mockResolvedValue([CARTE]);
    const vue = afficher(<Paiements flash={vi.fn()} />);

    await screen.findByText(/4242/);
    expect(vue.container.textContent).toMatch(/•••• 4242/);
    expect(vue.container.textContent).not.toMatch(/\d{13,}/);
  });

  it("annonce la garantie a l'ecran, pas seulement dans le code", async () => {
    afficher(<Paiements flash={vi.fn()} />);
    expect(await screen.findByText(/ne quitte jamais cette page/i)).toBeInTheDocument();
  });
});

describe("Securite", () => {
  it("exige le mot de passe actuel pour en changer", async () => {
    const util = userEvent.setup();
    afficher(<Securite user={UTILISATEUR} onProfil={vi.fn()} flash={vi.fn()} />);

    await util.click(screen.getAllByRole("button", { name: /modifier/i })[0]);
    await util.type(champ("Nouveau mot de passe"), "Hanabi-Negoro-2026!");
    await util.type(champ("Confirmer le mot de passe"), "Hanabi-Negoro-2026!");

    // Le bouton reste inerte tant que l'ancien mot de passe manque.
    expect(screen.getByRole("button", { name: /enregistrer/i })).toBeDisabled();
    expect(Compte.changerMotDePasse).not.toHaveBeenCalled();
  });

  it("refuse deux saisies divergentes", async () => {
    const util = userEvent.setup();
    afficher(<Securite user={UTILISATEUR} onProfil={vi.fn()} flash={vi.fn()} />);

    await util.click(screen.getAllByRole("button", { name: /modifier/i })[0]);
    await util.type(champ("Mot de passe actuel"), "ancien-mot-de-passe");
    await util.type(champ("Nouveau mot de passe"), "Hanabi-Negoro-2026!");
    await util.type(champ("Confirmer le mot de passe"), "PAS-LE-MEME-42!x");

    expect(screen.getByRole("button", { name: /enregistrer/i })).toBeDisabled();
  });

  it("previent que la nouvelle adresse devra etre confirmee", async () => {
    const util = userEvent.setup();
    afficher(<Securite user={UTILISATEUR} onProfil={vi.fn()} flash={vi.fn()} />);

    await util.click(screen.getAllByRole("button", { name: /modifier/i })[1]);

    // Dit AVANT la saisie : le decouvrir apres coup ressemblerait a une
    // regression.
    expect(screen.getByText(/devra être confirmée/i)).toBeInTheDocument();
  });
});
