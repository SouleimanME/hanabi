import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },

  // Tests unitaires et de composants (Vitest)
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/tests/setup.js"],
    // Vitest ne ramasse que `src/`
    include: ["src/**/*.{test,spec}.{js,jsx}"],
    // Les feuilles de style ne sont pas evaluees : aucun test n'affirme quoi que
    // ce soit sur la mise en forme, et les analyser couterait a chaque execution.
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{js,jsx}"],
      // Les dictionnaires et le contenu legal sont des donnees, pas du code : les
      // compter ferait chuter la couverture sans rien dire de sa qualite.
      exclude: ["src/i18n/dictionaries/**", "src/content/**", "src/tests/**", "src/main.jsx"],
    },
  },
  // Note de deploiement : la boutique sert plusieurs chemins (/produit/:id
});
