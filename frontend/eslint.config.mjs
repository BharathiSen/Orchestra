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
      // Enforced as an error. The session lives in a useSyncExternalStore hook
      // (lib/auth.ts useSession) and effects fetch, then set state in callbacks
      // behind a `cancelled` guard — see any page under app/projects/[id].
      "react-hooks/set-state-in-effect": "error",
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
