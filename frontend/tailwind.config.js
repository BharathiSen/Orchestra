/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // App shell: semantic tokens on the same dark palette as the landing
        // page, so the product reads as one thing from the first click.
        // Name what a colour is FOR, not what it looks like — `text-fg-muted`,
        // never `text-slate-600` — so a future theme change is one edit here.
        ground: "#0b0f14", // page background
        surface: "#141a22", // cards and panels
        raised: "#1a212b", // hover, selected rows, inputs
        line: {
          DEFAULT: "#232b36", // dividers and card borders
          strong: "#2e3846", // input and button borders
        },
        fg: {
          DEFAULT: "#e8edf4", // primary text
          muted: "#a3adba", // secondary text
          subtle: "#8a94a2", // labels and metadata
          faint: "#6b7685", // placeholders, pending states
        },
        // Brand action. Bright teal holds contrast on dark ground; text placed
        // on an accent fill uses `text-ground`.
        accent: "#2dd4bf",
        // Landing page only (its own CSS predates the app tokens).
        lp: {
          ground: "#0b0f14",
          panel: "#141a22",
          raised: "#1a212b",
          line: "#232b36",
          ink: "#e8edf4",
          dim: "#8a94a2",
          // Brand action, brightened so it holds contrast on the dark ground.
          beam: "#2dd4bf",
          // Reserved for money and measurement, never for actions — it reads as
          // instrument signal rather than a second brand colour.
          signal: "#e0a44a",
          ok: "#4ade80",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Segoe UI", "sans-serif"],
        display: ["var(--font-space)", "Georgia", "serif"],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};
