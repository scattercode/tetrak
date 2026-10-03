import js from "@eslint/js";
import stylistic from "@stylistic/eslint-plugin";
import globals from "globals";

// Matches the configuration on scattercode.dev and velostevie, so the three
// sites lint the same way and a habit learned on one transfers.
export default [
  js.configs.recommended,
  stylistic.configs.customize({
    indent: 2,
    quotes: "double",
    semi: true,
    arrowParens: false,
    braceStyle: "1tbs",
    commaDangle: "never"
  }),
  {
    files: ["assets/js/**/*.js"],
    languageOptions: {
      globals: globals.browser
    }
  },
  {
    // Build tooling: Node, not the browser.
    files: ["scripts/**/*.mjs", "*.config.mjs"],
    languageOptions: {
      globals: globals.node
    }
  },
  {
    // The Cloudflare Pages Functions that proxy Plausible. They live at the
    // repository root, one level above this config, because Cloudflare
    // resolves functions/ against the Pages root directory rather than the
    // site -- a functions/ inside site/ would never be found. ESLint will not
    // read files above its config, so `npm run lint:functions` runs from the
    // root with --config; this glob is relative to that. They run on workerd,
    // whose fetch/Request/Response/Headers are the browser set.
    files: ["functions/**/*.js"],
    languageOptions: {
      globals: globals.browser
    }
  },
  {
    rules: {
      "@stylistic/space-before-function-paren": ["error", { named: "never", anonymous: "always", asyncArrow: "always" }],
      "@stylistic/arrow-parens": ["error", "as-needed"],
      "@stylistic/operator-linebreak": ["error", "after", { overrides: { "?": "before", ":": "before" } }],
      "@stylistic/max-statements-per-line": "off",
      "no-unused-vars": ["error", { vars: "all", args: "after-used", argsIgnorePattern: "^_", caughtErrors: "none", ignoreRestSiblings: true }]
    }
  }
];
