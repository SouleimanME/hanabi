import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  // Note de deploiement : la boutique sert plusieurs chemins (/produit/:id,
  // /favoris, /compte...) resolus cote navigateur par `lib/routes.js`. Le
  // serveur de developpement de Vite renvoie index.html pour tout chemin
  // inconnu, ce qui suffit en local.
  //
  // En production, l'hebergeur doit faire la meme chose, sinon un lien partage
  // vers une fiche produit repondra 404 : redirection de toutes les routes vers
  // /index.html (regle « rewrite » chez Netlify et Vercel, `try_files $uri
  // /index.html` chez nginx).
  //
  // L'option `historyApiFallback` qui figurait ici n'existe pas dans Vite -
  // elle appartient a webpack-dev-server et etait silencieusement ignoree.
});
