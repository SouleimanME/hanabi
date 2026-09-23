/** Parcours de bout en bout : navigateur, API et base réels.
 *
 * L'API pointe sur un SQLite jetable (le parcours écrit des commandes), sans
 * comptes de démonstration ni tâche de fond.
 */
import { defineConfig, devices } from "@playwright/test";

const PORT_FRONT = 5174;
const PORT_API = 8001;

// Python du venv du backend ; `PYTHON` le remplace en intégration continue
const PYTHON =
  process.env.PYTHON ||
  (process.platform === "win32"
    ? "../hanabi-back/.venv/Scripts/python.exe"
    : "../hanabi-back/.venv/bin/python");

export default defineConfig({
  testDir: "./e2e",
  // La première navigation attend le démarrage de Vite
  timeout: 60_000,
  expect: { timeout: 10_000 },

  // En série : les tests partagent le stock du même catalogue
  fullyParallel: false,
  workers: 1,

  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,

  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],

  use: {
    baseURL: `http://localhost:${PORT_FRONT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: [
    {
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
