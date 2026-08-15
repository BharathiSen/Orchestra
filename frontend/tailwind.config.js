/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        mist: "#e2e8f0",
        accent: "#0d9488",
        panel: "#f8fafc",
        // Landing page only. Namespaced under `lp` because the app shell is
        // light-themed and already owns `ink`, `panel`, and `accent` — a flat
        // dark palette here would collide with all three.
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
