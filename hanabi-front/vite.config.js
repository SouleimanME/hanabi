import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },

  // Tests unitaires et de composants (Vitest). Ils partagent la configuration de
  // Vite a dessein : les tests resolvent les modules exactement comme le fait la
  // construction, si bien qu'un test ne peut pas passer sur un graphe de
  // dependances que la production n'a jamais.
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/tests/setup.js"],
    // Vitest ne ramasse que `src/`. Sans cette borne, il chargeait aussi les
    // parcours Playwright de `e2e/` - deux coureurs, deux API `test()`
    // incompatibles - et le fichier echouait au chargement sans qu'aucun test
    // n'echoue, ce qui donne un decompte contradictoire : « 1 fichier en echec,
    // 188 tests passes ».
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
  // Note de deploiement : la boutique sert plusieurs chemins (/produit/:id,
  // /favoris, /compte...) resolus cote navigateur par `lib/routes.js`. Le
  // serveur de developpement de Vite renvoie index.html pour tout chemin
  // inconnu, ce qui suffit en local.
  //
  // En production, l'hebergeur doit faire la meme chose, sinon un lien partage
  // vers une fiche produit repondra 404 : redirection de toutes les routes vers
  // /index.html (fichier `public/_redirects` chez Cloudflare Pages, `try_files
  // $uri /index.html` chez nginx).
  //
  // L'option `historyApiFallback` qui figurait ici n'existe pas dans Vite -
  // elle appartient a webpack-dev-server et etait silencieusement ignoree.
});
