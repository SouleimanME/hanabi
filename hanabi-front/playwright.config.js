/** Parcours de bout en bout : un vrai navigateur, une vraie API, une vraie base.
 *
 * CE QUE CES TESTS APPORTENT que les 538 autres n'apportent pas. Les tests
 * unitaires verifient des pieces, les tests d'API verifient des contrats. Aucun
 * des deux ne repond a « est-ce qu'on peut acheter ». Entre les deux vivent le
 * cablage, le routage, la serialisation, l'ordre des appels et l'etat partage -
 * et c'est la que casse un tunnel d'achat.
 *
 * BASE ISOLEE, ET CE N'EST PAS UN DETAIL. L'API demarree ici pointe sur un
 * fichier SQLite jetable, jamais sur la base de developpement : un parcours
 * d'achat ECRIT - il decremente du stock, cree des commandes, inscrit des
 * courriels. Le faire tourner sur une base reelle salirait des donnees a chaque
 * execution, et la premiere personne a lancer la suite s'en apercevrait trop
 * tard.
 *
 * `DEMO_USERS=0` coupe la generation des cent mille comptes de demonstration :
 * elle prend plusieurs minutes et n'apporte rien a un tunnel d'achat.
 * `OUTBOX_INTERVALLE_SECONDES=0` empeche l'ouvrier de fond de partir, pour que
 * rien ne s'execute en dehors de ce que le test declenche.
 */
import { defineConfig, devices } from "@playwright/test";

const PORT_FRONT = 5174;
const PORT_API = 8001;

/* Interpreteur Python du backend.
 *
 * Le venv du projet, et non le Python du systeme : celui-ci n'a aucune des
 * dependances de l'API, et l'erreur qu'il produit - « No module named
 * slowapi » - ne dit pas d'ou vient le probleme.
 *
 * `PYTHON` permet de pointer ailleurs sans toucher au fichier, ce dont
 * l'integration continue a besoin : elle installe les dependances dans son
 * propre environnement, sans venv. */
const PYTHON =
  process.env.PYTHON ||
  (process.platform === "win32"
    ? "../hanabi-back/.venv/Scripts/python.exe"
    : "../hanabi-back/.venv/bin/python");

export default defineConfig({
  testDir: "./e2e",
  // Un parcours complet traverse le reseau, une base et un rendu : la seconde
  // par defaut de Playwright est trop courte pour la premiere navigation, qui
  // attend le demarrage de Vite.
  timeout: 60_000,
  expect: { timeout: 10_000 },

  // En serie. Ces tests partagent une base et un catalogue : deux parcours
  // simultanes se disputeraient le stock du meme article, et l'echec ne dirait
  // rien du code.
  fullyParallel: false,
  workers: 1,

  // Aucun reessai en local : un test instable doit se voir. En integration
  // continue, un seul - le temps de distinguer une vraie regression d'un alea
  // de machine partagee.
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,

  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],

  use: {
    baseURL: `http://localhost:${PORT_FRONT}`,
    // Trace et capture seulement en cas d'echec : un test vert n'a rien a
    // raconter, et conserver ses artefacts remplit le disque pour rien.
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: [
    {
      // Base jetable, catalogue seul, aucune tache de fond.
      command: [
        `"${PYTHON}" -c "import os, uvicorn;`,
        "os.chdir('../hanabi-back');",
        `uvicorn.run('app.main:app', port=${PORT_API})"`,
      ].join(" "),
      port: PORT_API,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        DATABASE_URL: "sqlite:///./e2e.db",
        SECRET_KEY: "cle-de-test-e2e-sans-valeur-en-production",
        ENV: "dev",
        DEMO_USERS: "0",
        OUTBOX_INTERVALLE_SECONDES: "0",
        MAIL_BACKEND: "memoire",
        PUBLIC_ADMIN_DEMO: "1",
        CORS_ORIGINS: `http://localhost:${PORT_FRONT}`,
      },
    },
    {
      command: `npm run dev -- --port ${PORT_FRONT} --strictPort`,
      port: PORT_FRONT,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { VITE_API_URL: `http://localhost:${PORT_API}` },
    },
  ],
});
