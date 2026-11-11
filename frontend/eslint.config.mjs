// eslint-config-next 16 ships native flat configs, so they are spread in
// directly. (Next 15 needed a FlatCompat bridge; that bridge now fails on the
// new config's circular plugin references.)
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const config = [
  {
    ignores: [
      ".next/**",
      ".open-next/**",
      ".wrangler/**",
      "node_modules/**",
      "next-env.d.ts",
    ],
  },
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    // Build configuration is CommonJS by necessity — Next.js loads
    // next.config.js before any ESM transform, so require() is correct here.
    files: ["*.config.js", "*.config.cjs", "postcss.config.js", "tailwind.config.js"],
    rules: {
      "@typescript-eslint/no-require-imports": "off",
    },
  },
  {
    rules: {
      // New in the React-Compiler-era hooks plugin that ships with Next 16.
      // All 16 hits are one pattern: read the session from localStorage (or
      // start a client fetch) after mount, then set state. That is how browser-
      // only state has to enter a prerendered page; the rule's preferred fix is
      // a useSyncExternalStore-based session hook, which is a refactor of every
      // page, not part of a framework upgrade. Kept visible as a warning so the
      // refactor stays on the list instead of being silenced.
      "react-hooks/set-state-in-effect": "warn",
      // Unused variables are a real signal in this codebase; the underscore
      // prefix is the documented way to mark a deliberate discard.
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
    },
  },
];

export default config;
