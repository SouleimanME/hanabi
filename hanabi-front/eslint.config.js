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

  // Les tests tournent sous Node, pas dans le navigateur
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
      // La fixture de Playwright se declare `async ({ page }, use) => ...`
      "react-hooks/rules-of-hooks": "off",
    },
  },
];
