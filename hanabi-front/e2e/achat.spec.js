/** Parcours d'achat complet : trouver un objet, payer, recevoir la confirmation. */
import { test, expect, ouvrirBoutique, ajouterPremierArticle, ouvrirPanier } from "./fixtures.js";

const LIVRAISON = {
  prenom: "Ada",
  nom: "Lovelace",
  adresse: "12 rue des Érables",
  cp: "75011",
  ville: "Paris",
};

const formulaire = (page) => page.locator(".checkout-form");

async function remplirLivraison(page, email = "ada@hanabi.fr") {
  await formulaire(page)
    .getByLabel(/^E-mail$/i)
    .fill(email);
  await formulaire(page)
    .getByLabel(/^Prénom$/i)
    .fill(LIVRAISON.prenom);
  await formulaire(page).getByLabel(/^Nom$/i).fill(LIVRAISON.nom);
  await formulaire(page)
    .getByLabel(/^Adresse$/i)
    .fill(LIVRAISON.adresse);
  await formulaire(page)
    .getByLabel(/^Code postal$/i)
    .fill(LIVRAISON.cp);
  await formulaire(page)
    .getByLabel(/^Ville$/i)
    .fill(LIVRAISON.ville);
}

/** Tapée touche par touche, comme une personne : un remplissage d'un bloc
 *  masquait le passage au champ suivant, qui jugeait le numéro à quinze chiffres. */
async function remplirCarte(page, numero = "4242 4242 4242 4242") {
  await formulaire(page)
    .getByLabel(/Numéro de carte/i)
    .pressSequentially(numero.replace(/\s/g, ""));
  await expect(formulaire(page).getByLabel(/^Expiration$/i)).toBeFocused();
  await page.keyboard.type("1230");
  await expect(formulaire(page).getByLabel(/^Cryptogramme$/i)).toBeFocused();
  await page.keyboard.type("123");
  await expect(formulaire(page).locator(".field-error")).toHaveCount(0);
}

// Case jamais pré-cochée : on la coche comme une personne le ferait
const caseConditions = (page) => page.getByRole("checkbox", { name: /conditions générales/i });

test.describe("Tunnel d'achat", () => {
  test("un invité peut acheter de bout en bout", async ({ page }) => {
    await ouvrirBoutique(page);
    const nom = await ajouterPremierArticle(page);

    const tiroir = await ouvrirPanier(page);
    await expect(tiroir).toContainText(nom);

    await tiroir.getByRole("button", { name: /passer la commande/i }).click();
    await expect(page).toHaveURL(/\/commande/);

    await remplirLivraison(page);
    await remplirCarte(page);
    await caseConditions(page).check();
    await page.getByRole("button", { name: /^payer/i }).click();

    await expect(page.getByRole("heading", { name: /commande confirmée/i })).toBeVisible();
    await expect(page.locator("body")).toContainText(/ATL\d{6}/);
    await expect(page).toHaveURL(/\/merci/);
  });

  test("le panier survit à un rechargement", async ({ page }) => {
    await ouvrirBoutique(page);
    const nom = await ajouterPremierArticle(page);

    await page.reload();
    await expect(page.locator(".case").first()).toBeVisible();

    await expect(await ouvrirPanier(page)).toContainText(nom);
  });

  test("un code promo change le total calculé par le serveur", async ({ page }) => {
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);

    const tiroir = await ouvrirPanier(page);
    const total = tiroir.locator(".totals-total dd");
    const avant = await total.innerText();

    await tiroir.getByLabel(/^code promo$/i).fill("BIENVENUE10");
    await tiroir.getByRole("button", { name: /^appliquer$/i }).click();

    await expect(tiroir.locator(".totals")).toContainText(/remise/i);
    await expect(total).not.toHaveText(avant);
  });

  test("un code promo inventé est refusé", async ({ page }) => {
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);

    const tiroir = await ouvrirPanier(page);
    await tiroir.getByLabel(/^code promo$/i).fill("CODEBIDON99");
    await tiroir.getByRole("button", { name: /^appliquer$/i }).click();

    await expect(tiroir.locator(".promo .field-error")).toBeVisible();
    await expect(tiroir.locator(".totals")).not.toContainText(/remise/i);
  });

  test("un réessai après coupure réseau réutilise la même clé", async ({ page }) => {
    // Le bouton se désactive pendant l'envoi : le double clic est impossible.
    // La clé sert au réessai après une coupure, simulée ici sur la première requête.
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);

    await (await ouvrirPanier(page)).getByRole("button", { name: /passer la commande/i }).click();
    await remplirLivraison(page);
    await remplirCarte(page);
    await caseConditions(page).check();

    const cles = [];
    let premiereCoupee = false;
    await page.route("**/orders/checkout", async (route) => {
      cles.push(route.request().headers()["idempotency-key"]);
      if (!premiereCoupee) {
        premiereCoupee = true;
        return route.abort("connectionfailed");
      }
      return route.continue();
    });

    const bouton = page.getByRole("button", { name: /^payer/i });
    await bouton.click();
    await expect(page.locator(".notice-error")).toBeVisible();
    await expect(bouton).toBeEnabled();

    await bouton.click();
    await expect(page.getByRole("heading", { name: /commande confirmée/i })).toBeVisible();

    expect(cles).toHaveLength(2);
    expect(cles[0]).toBeTruthy();
    expect(cles[0]).toBe(cles[1]);
  });

  test("payer sans accepter les conditions est refusé", async ({ page }) => {
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);

    await (await ouvrirPanier(page)).getByRole("button", { name: /passer la commande/i }).click();
    await remplirLivraison(page);
    await remplirCarte(page);
    await expect(caseConditions(page)).not.toBeChecked();

    await page.getByRole("button", { name: /^payer/i }).click();

    await expect(page.locator(".notice-error")).toBeVisible();
    await expect(page).toHaveURL(/\/commande/);
  });

  test("un formulaire vide dit quoi corriger, champ par champ", async ({ page }) => {
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);
    await (await ouvrirPanier(page)).getByRole("button", { name: /passer la commande/i }).click();

    await page.getByRole("button", { name: /^payer/i }).click();

    // Le focus part sur le premier champ fautif, et chaque erreur est sous son champ
    await expect(formulaire(page).getByLabel(/^E-mail$/i)).toBeFocused();
    await expect(formulaire(page).getByLabel(/^Ville$/i)).toHaveAttribute("aria-invalid", "true");
    await expect(page.locator(".notice-error")).toContainText(/champs sont à corriger/);
  });

  test("la carte de test du refus montre le refus de la banque", async ({ page }) => {
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);
    await (await ouvrirPanier(page)).getByRole("button", { name: /passer la commande/i }).click();

    await remplirLivraison(page);
    await remplirCarte(page, "4000 0000 0000 0002");
    await caseConditions(page).check();
    await page.getByRole("button", { name: /^payer/i }).click();

    await expect(page.locator(".notice-error")).toContainText(/refusée/i);
    await expect(page).toHaveURL(/\/commande/);
  });
});

test.describe("Formulaire de paiement", () => {
  async function allerAuPaiement(page) {
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);
    await (await ouvrirPanier(page)).getByRole("button", { name: /passer la commande/i }).click();
    await expect(page).toHaveURL(/\/commande/);
  }

  test("une adresse proposée remplit rue, code postal et ville", async ({ page }) => {
    await page.route("https://data.geopf.fr/**", (route) =>
      route.fulfill({
        json: {
          features: [
            {
              properties: {
                id: "69382_1",
                type: "housenumber",
                name: "8 Rue Mercière",
                postcode: "69002",
                city: "Lyon",
              },
            },
          ],
        },
      }),
    );
    await allerAuPaiement(page);

    const adresse = formulaire(page).getByRole("combobox", { name: /^Adresse$/i });
    await adresse.pressSequentially("8 rue merc");
    await page.getByRole("option", { name: /8 Rue Mercière/ }).click();

    await expect(adresse).toHaveValue("8 Rue Mercière");
    await expect(formulaire(page).getByLabel(/^Code postal$/i)).toHaveValue("69002");
    await expect(formulaire(page).getByLabel(/^Ville$/i)).toHaveValue("Lyon");
  });

  test("le code postal refuse les lettres", async ({ page }) => {
    await allerAuPaiement(page);
    const cp = formulaire(page).getByLabel(/^Code postal$/i);
    await cp.pressSequentially("75a01b1");
    await expect(cp).toHaveValue("75011");
  });

  test("seize chiffres faux sont signalés comme invalides, pas incomplets", async ({ page }) => {
    await allerAuPaiement(page);
    await formulaire(page)
      .getByLabel(/Numéro de carte/i)
      .fill("4213 7213 8213 9821");
    await expect(formulaire(page).locator(".field-error")).toHaveText(/Numéro invalide/);
  });

  test("le logo du réseau remplace les cartes acceptées", async ({ page }) => {
    await allerAuPaiement(page);
    const logos = formulaire(page).locator(".card-logos img");
    await expect(logos).toHaveCount(3);
    await formulaire(page)
      .getByLabel(/Numéro de carte/i)
      .fill("5555 5555 5555 4444");
    await expect(logos).toHaveCount(1);
    await expect(logos).toHaveAttribute("src", "/cartes/mastercard.svg");
    await expect(formulaire(page).locator(".card-issuer")).toHaveText("Carte de test");
  });
});

test.describe("Navigation", () => {
  test("l'onglet porte le nom de la fiche ouverte", async ({ page }) => {
    await ouvrirBoutique(page);
    await expect(page).toHaveTitle(/^Hanabi/);
    await page.locator(".case-open").first().click();
    const nom = await page.locator(".product-name").innerText();
    await expect(page).toHaveTitle(new RegExp(`^${nom}`));
  });

  test("une fiche produit se partage par son adresse", async ({ page }) => {
    await ouvrirBoutique(page);
    await page.locator(".case-open").first().click();
    await expect(page).toHaveURL(/\/produit\/\d+/);

    const adresse = page.url();
    const titre = await page.locator(".product-name").innerText();

    await page.goto(adresse);
    await expect(page.locator(".product-name")).toHaveText(titre);
  });

  test("le bouton Retour du navigateur parcourt les écrans", async ({ page }) => {
    await ouvrirBoutique(page);
    await page.locator(".case-open").first().click();
    await expect(page).toHaveURL(/\/produit\/\d+/);

    await page.goBack();
    await expect(page).toHaveURL(/localhost:\d+\/$/);
    await expect(page.locator(".case").first()).toBeVisible();
  });

  test("une adresse inconnue retombe sur l'accueil", async ({ page }) => {
    await page.goto("/rubrique-qui-nexiste-pas");
    await expect(page.locator(".case").first()).toBeVisible({ timeout: 30_000 });
  });
});
