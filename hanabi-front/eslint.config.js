import js from "@eslint/js";
import globals from "globals";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default [
  { ignores: ["dist", "node_modules"] },
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: globals.browser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: { react: { version: "detect" } },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...react.configs.recommended.rules,
      ...react.configs["jsx-runtime"].rules,
      ...reactHooks.configs.recommended.rules,

      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],

      // Le projet ne documente pas ses props via PropTypes : les composants
      // sont internes et leurs contrats sont decrits en JSDoc.
      "react/prop-types": "off",

      // Un catch vide est un choix explicite ici (stockage indisponible,
      // reponse sans corps JSON) ; il est toujours commente.
      "no-empty": ["error", { allowEmptyCatch: true }],

      "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },

  // Les tests tournent sous Node, pas dans le navigateur : ils lisent des
  // fichiers et interrogent des chemins. Sans ce bloc, `process` ou `console`
  // seraient signales comme indefinis dans les seuls fichiers qui ont le droit
  // de s'en servir.
  {
    files: ["**/*.test.{js,jsx}", "src/tests/**/*.js"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },

  // Outillage : parcours de bout en bout et scripts de construction. Ces
  // fichiers tournent sous Node et non dans le navigateur.
  {
    files: ["e2e/**/*.js", "playwright.config.js", "scripts/**/*.js"],
    languageOptions: {
      globals: { ...globals.node },
    },
    rules: {
      // La fixture de Playwright se declare `async ({ page }, use) => ...` :
      // `use` y est un parametre, pas le hook React du meme nom. La regle ne
      // peut pas faire la difference, et n'a de toute facon rien a verifier
      // dans un fichier sans composant.
      "react-hooks/rules-of-hooks": "off",
    },
  },
];
