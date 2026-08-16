/** LE parcours : trouver un objet, l'acheter, recevoir sa confirmation.
 *
 * C'est le seul chemin dont l'echec coute de l'argent, et le seul qu'aucun test
 * unitaire ne couvre : chaque piece est verifiee ailleurs, mais rien ne
 * verifiait qu'elles s'emboitent.
 */
import { test, expect, ouvrirBoutique, ajouterPremierArticle, ouvrirPanier } from "./fixtures.js";

const LIVRAISON = {
  prenom: "Ada",
  nom: "Lovelace",
  adresse: "12 rue des Erables",
  cp: "75011",
  ville: "Paris",
};

async function remplirLivraison(page, email = "ada@hanabi.fr") {
  await page.getByLabel(/^E-mail/i).fill(email);
  await page.getByLabel(/^Prénom/i).fill(LIVRAISON.prenom);
  await page.getByLabel(/^Nom/i).fill(LIVRAISON.nom);
  await page.getByLabel(/^Adresse$/i).fill(LIVRAISON.adresse);
  await page.getByLabel(/Code postal/i).fill(LIVRAISON.cp);
  await page.getByLabel(/^Ville/i).fill(LIVRAISON.ville);
}

async function remplirCarte(page, numero = "4242 4242 4242 4242") {
  await page.getByLabel(/Numéro de carte/i).fill(numero);
  await page.getByLabel(/Expiration/i).fill("12/30");
  await page.getByLabel(/^CVC$/i).fill("123");
}

/** Coche l'acceptation des conditions de vente.
 *
 * Jamais pre-cochee : c'est la regle, et le test la suit plutot que de la
 * contourner. Une aide qui forcerait la case par `evaluate` masquerait le jour
 * ou elle disparaitrait de l'ecran.
 */
async function accepterLesConditions(page) {
  await page.locator(".co-cgv input[type=checkbox]").check();
}

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
    await accepterLesConditions(page);
    await page.getByRole("button", { name: /^payer/i }).click();

    // Confirmation : numero de commande et adresse de recapitulatif.
    await expect(page.getByRole("heading", { name: /commande confirmée/i })).toBeVisible();
    await expect(page.locator("body")).toContainText(/ATL\d{6}/);
    await expect(page).toHaveURL(/\/merci/);
  });

  test("le panier survit à un rechargement", async ({ page }) => {
    // Le panier vit dans le localStorage : ce test verifie que l'etat repart
    // du stockage et non d'un souvenir en memoire.
    await ouvrirBoutique(page);
    const nom = await ajouterPremierArticle(page);

    await page.reload();
    await expect(page.locator(".card").first()).toBeVisible();

    await expect(await ouvrirPanier(page)).toContainText(nom);
  });

  test("un code promo change le total, et le serveur a le dernier mot", async ({ page }) => {
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);

    const tiroir = await ouvrirPanier(page);
    const avant = await tiroir.locator(".sum-row.total").innerText();

    await tiroir.getByPlaceholder(/code promo/i).fill("BIENVENUE10");
    await tiroir.getByRole("button", { name: /^appliquer$/i }).click();

    // Le total recalcule vient de `POST /orders/quote` : c'est la reponse du
    // serveur qu'on lit, jamais un calcul du navigateur.
    await expect(tiroir.locator(".sum-row.disc")).toBeVisible();
    await expect(tiroir.locator(".sum-row.total")).not.toHaveText(avant);
  });

  test("un code promo inventé est refusé", async ({ page }) => {
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);

    const tiroir = await ouvrirPanier(page);
    await tiroir.getByPlaceholder(/code promo/i).fill("CODEBIDON99");
    await tiroir.getByRole("button", { name: /^appliquer$/i }).click();

    await expect(tiroir.locator(".promo-err")).toBeVisible();
    await expect(tiroir.locator(".sum-row.disc")).toHaveCount(0);
  });

  test("un réessai après coupure réseau réutilise la même clé", async ({ page }) => {
    /* LA propriete que seul un test de bout en bout peut verifier.
     *
     * L'idempotence repose sur une cle tiree par le NAVIGATEUR et CONSERVEE
     * entre deux tentatives. Les tests d'API la verifient en envoyant deux fois
     * la meme cle - mais rien ne prouvait que le navigateur la repete vraiment.
     * Une cle regeneree a chaque appel passerait tous les tests serveur et ne
     * protegerait de rien.
     *
     * LE SCENARIO A CHANGE en cours d'ecriture, et l'echec du premier etait
     * instructif : un double-clic litteral est IMPOSSIBLE par l'interface,
     * puisque le bouton se desactive pendant l'envoi puis disparait avec
     * l'ecran. C'est une bonne chose, mais cela veut dire que la cle ne protege
     * pas de la ou on la croyait. Elle protege du reessai APRES une coupure -
     * un reseau qui tombe, un telephone qui repart - et c'est ce cas-la qu'on
     * reproduit ici en coupant la premiere requete.
     */
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);

    await (await ouvrirPanier(page)).getByRole("button", { name: /passer la commande/i }).click();
    await remplirLivraison(page);
    await remplirCarte(page);
    await accepterLesConditions(page);

    const cles = [];
    let premiereCoupee = false;
    await page.route("**/orders/checkout", async (route) => {
      cles.push(route.request().headers()["idempotency-key"]);
      if (!premiereCoupee) {
        premiereCoupee = true;
        // Coupure franche, comme un reseau qui tombe : la requete est peut-etre
        // arrivee au serveur, le navigateur n'en saura jamais rien.
        return route.abort("connectionfailed");
      }
      return route.continue();
    });

    const bouton = page.getByRole("button", { name: /^payer/i });
    await bouton.click();
    // L'echec est annonce, et le bouton redevient actionnable : sans cela il
    // n'y aurait aucun moyen de reessayer.
    await expect(page.locator(".form-err")).toBeVisible();
    await expect(bouton).toBeEnabled();

    await bouton.click();
    await expect(page.getByRole("heading", { name: /commande confirmée/i })).toBeVisible();

    // Les DEUX tentatives portent la meme cle. C'est elle qui permet au serveur
    // de reconnaitre un rejeu si la premiere requete l'avait bel et bien
    // atteint.
    expect(cles).toHaveLength(2);
    expect(cles[0]).toBeTruthy();
    expect(cles[0]).toBe(cles[1]);
  });

  test("payer sans accepter les conditions est refusé", async ({ page }) => {
    /* Obligatoire en vente à distance. Le serveur refuse aussi — c'est vérifié
     * côté API — mais ce parcours prouve que la case existe bel et bien à
     * l'écran et qu'elle bloque. Une règle qui ne vit que dans les tests
     * d'API ne protège personne. */
    await ouvrirBoutique(page);
    await ajouterPremierArticle(page);

    await (await ouvrirPanier(page)).getByRole("button", { name: /passer la commande/i }).click();
    await remplirLivraison(page);
    await remplirCarte(page);
    // La case reste décochée : jamais pré-cochée, c'est la règle.
    await expect(page.locator(".co-cgv input[type=checkbox]")).not.toBeChecked();

    await page.getByRole("button", { name: /^payer/i }).click();

    await expect(page.locator(".form-err")).toBeVisible();
    await expect(page).toHaveURL(/\/commande/);
  });
});

test.describe("Navigation", () => {
  test("une fiche produit est partageable par son adresse", async ({ page }) => {
    await ouvrirBoutique(page);
    await page.locator(".card-art").first().click();
    await expect(page).toHaveURL(/\/produit\/\d+/);

    const adresse = page.url();
    const titre = await page.locator(".pp-name").innerText();

    // Rechargement direct sur l'adresse : c'est ce que fait quelqu'un a qui on
    // envoie le lien.
    await page.goto(adresse);
    await expect(page.locator(".pp-name")).toHaveText(titre);
  });

  test("le bouton Retour du navigateur parcourt les écrans", async ({ page }) => {
    await ouvrirBoutique(page);
    await page.locator(".card-art").first().click();
    await expect(page).toHaveURL(/\/produit\/\d+/);

    await page.goBack();
    await expect(page).toHaveURL(/localhost:\d+\/$/);
    await expect(page.locator(".card").first()).toBeVisible();
  });

  test("une adresse inconnue retombe sur l'accueil sans écran vide", async ({ page }) => {
    await page.goto("/rubrique-qui-nexiste-pas");
    await expect(page.locator(".card").first()).toBeVisible({ timeout: 30_000 });
  });
});
