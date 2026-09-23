/** Aides communes aux parcours de bout en bout. */
import { test as base, expect } from "@playwright/test";

/** Adresses renvoyées par défaut : aucune. Les parcours ne dépendent pas du
 *  service de l'IGN ; un test qui veut des propositions pose les siennes. */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route("https://data.geopf.fr/**", (route) =>
      route.fulfill({ json: { type: "FeatureCollection", features: [] } }),
    );
    await use(page);
  },
});

export { expect };

/** Ajoute au panier le premier objet du plateau et rend son nom. */
export async function ajouterPremierArticle(page) {
  const casePlateau = page.locator(".case").first();
  await expect(casePlateau).toBeVisible();
  const nom = (await casePlateau.locator(".case-name").innerText()).trim();
  await casePlateau.getByRole("button", { name: /au panier$/i }).click();
  return nom;
}

/** Ouvre le panier ; l'ajout d'un article ne l'ouvre pas. */
export async function ouvrirPanier(page) {
  await page
    .locator(".hd")
    .getByRole("button", { name: /^ouvrir le panier/i })
    .click();
  const tiroir = page.locator(".sheet-cart");
  await expect(tiroir).toHaveAttribute("data-open", "true");
  return tiroir;
}

/** Attend que le catalogue soit chargé. */
export async function ouvrirBoutique(page) {
  await page.goto("/");
  await expect(page.locator(".case").first()).toBeVisible({ timeout: 30_000 });
}
