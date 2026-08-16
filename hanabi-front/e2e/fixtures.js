/** Socle commun aux parcours de bout en bout.
 *
 * DEUX BRUITS DE FOND SONT COUPES ICI, et seulement eux : l'offre de bienvenue,
 * qui s'ouvre par-dessus la page au bout de quelques secondes, et le panier
 * herite d'un test precedent. Les couper d'entree vaut mieux que de les fermer
 * par un clic - un clic sur une fenetre qui n'est pas encore la echoue, un clic
 * sur une fenetre deja fermee aussi, et le test devient instable pour une raison
 * qui n'a rien a voir avec ce qu'il verifie.
 *
 * Tout le reste est laisse intact. En particulier, les barrieres anti-robots ne
 * sont PAS desactivees : le parcours les traverse pour de vrai, ce qui detecte
 * une regression de cablage que des tests d'API ne verraient pas.
 */
import { test as base, expect } from "@playwright/test";

export const test = base.extend({
  page: async ({ page }, use) => {
    // `addInitScript` s'execute AVANT le code de la page, a chaque navigation :
    // c'est la seule facon de poser un `localStorage` que l'application lira
    // des son premier rendu. Le poser apres coup arriverait trop tard.
    await page.addInitScript(() => {
      // « deja repondu » : l'offre ne s'ouvrira pas. Repose a chaque navigation,
      // ce qui est sans effet - la valeur est la meme.
      window.localStorage.setItem("hanabi:welcome", JSON.stringify("no"));
    });

    // LE PANIER N'EST PAS VIDE ICI, et c'etait une erreur de le faire.
    //
    // `addInitScript` s'execute avant CHAQUE navigation, rechargement compris :
    // vider le panier a cet endroit effacait ce que le test « le panier survit
    // a un rechargement » venait precisement d'y mettre. La fixture faisait
    // echouer le test qu'elle etait censee servir.
    //
    // C'est inutile de toute facon : Playwright ouvre un contexte neuf par
    // test, donc un `localStorage` vide.
    await use(page);
  },
});

export { expect };

/** Ajoute au panier le premier article disponible de la grille.
 *
 * Rend le nom de l'article : les tests suivants s'en servent pour verifier que
 * c'est bien LUI qu'on retrouve au panier, plutot que de faire confiance a
 * l'ordre d'affichage.
 */
export async function ajouterPremierArticle(page) {
  const carte = page.locator(".card").first();
  await expect(carte).toBeVisible();
  const nom = (await carte.locator(".card-name, h3").first().innerText()).trim();
  await carte.getByRole("button", { name: /ajouter/i }).click();
  return nom;
}

/** Ouvre le tiroir du panier et attend qu'il soit en place.
 *
 * L'ajout au panier N'OUVRE PAS le tiroir : il incremente le compteur de
 * l'en-tete et affiche une notification, rien de plus. C'est un bon choix - une
 * fenetre qui s'ouvre a chaque ajout interrompt quelqu'un qui en met trois -
 * mais il fallait le constater plutot que le supposer. Cette aide existe pour
 * qu'aucun test ne refasse l'hypothese.
 */
export async function ouvrirPanier(page) {
  // REMONTER D'ABORD. L'en-tete se masque au defilement (`useHideOnScroll`) et
  // se retablit en glissant. Playwright fait defiler pour amener un bouton dans
  // le champ de vision, ce defilement relance l'animation, le bouton bouge, et
  // le controle de stabilite recommence - jusqu'au delai d'attente. Un bouton
  // deja en haut de page n'a nulle part ou aller.
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);

  await page
    .locator(".hd")
    .getByRole("button", { name: /^panier$/i })
    .click();
  const tiroir = page.locator(".drawer");
  await expect(tiroir).toHaveClass(/open/);
  return tiroir;
}

/** Attend que le catalogue soit charge et affiche. */
export async function ouvrirBoutique(page) {
  await page.goto("/");
  await expect(page.locator(".card").first()).toBeVisible({ timeout: 30_000 });
}
