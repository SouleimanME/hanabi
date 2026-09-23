/** Bandeau cookies : refuser aussi simple qu'accepter, et un refus tenu. */
import { test, expect, ouvrirBoutique } from "./fixtures.js";

const VUE = /\/products\/\d+\/view$/;

test.describe("Cookies", () => {
  test("refuser et accepter sont au même niveau, et le choix est retenu", async ({ page }) => {
    await ouvrirBoutique(page);
    const bandeau = page.getByRole("region", { name: "Mesure d'audience" });
    await expect(bandeau).toBeVisible();
    await expect(bandeau.getByRole("button", { name: "Tout accepter" })).toBeVisible();

    await bandeau.getByRole("button", { name: "Tout refuser" }).click();
    await expect(bandeau).toBeHidden();

    await page.reload();
    await expect(page.locator(".case").first()).toBeVisible();
    await expect(page.getByRole("region", { name: "Mesure d'audience" })).toBeHidden();
  });

  test("sans accord, une fiche consultée n'est pas rattachée au compte", async ({ page }) => {
    // Un client connecté : le jeton est là, seul le bandeau décide de l'envoyer
    await page.addInitScript(() => localStorage.setItem("hanabi:token", "jeton-de-test"));
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        json: { id: 1, name: "Client Test", email: "client@test.fr", is_admin: false },
      }),
    );
    await ouvrirBoutique(page);
    await page.getByRole("button", { name: "Tout refuser" }).click();

    const [refusee] = await Promise.all([
      page.waitForRequest(VUE),
      page.locator(".case-open").first().click(),
    ]);
    expect(refusee.headers().authorization).toBeUndefined();

    // Accord donné depuis le pied de page : la consultation suivante porte le jeton
    await page.goto("/");
    await page.getByRole("button", { name: "Gérer mes cookies" }).click();
    await page.getByRole("button", { name: "Tout accepter" }).click();
    const [acceptee] = await Promise.all([
      page.waitForRequest(VUE),
      page.locator(".case-open").nth(1).click(),
    ]);
    expect(acceptee.headers().authorization).toBe("Bearer jeton-de-test");
  });
});
