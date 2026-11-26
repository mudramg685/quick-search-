/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["'IBM Plex Sans'", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        display: ["'Instrument Serif'", "ui-serif", "Georgia", "serif"],
        read: ["var(--font-read)"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        "surface-2": "rgb(var(--surface-2) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        "ink-2": "rgb(var(--ink-2) / <alpha-value>)",
        "ink-3": "rgb(var(--ink-3) / <alpha-value>)",
        brand: "rgb(var(--brand) / <alpha-value>)",
        "on-brand": "rgb(var(--on-brand) / <alpha-value>)",
      },
      boxShadow: {
        soft: "0 1px 2px rgb(0 0 0 / 0.05), 0 4px 14px -6px rgb(0 0 0 / 0.10)",
        lift: "0 2px 6px rgb(0 0 0 / 0.06), 0 16px 36px -16px rgb(0 0 0 / 0.22)",
      },
    },
  },
  plugins: [],
};
