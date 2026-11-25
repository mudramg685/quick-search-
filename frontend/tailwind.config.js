/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        display: ["'Inter Tight'", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ["'Instrument Serif'", "ui-serif", "Georgia", "serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
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
        "brand-2": "rgb(var(--brand-2) / <alpha-value>)",
        "brand-ink": "rgb(var(--brand-ink) / <alpha-value>)",
      },
      boxShadow: {
        soft: "0 1px 2px rgb(0 0 0 / 0.04), 0 8px 24px -12px rgb(0 0 0 / 0.12)",
        lift: "0 2px 4px rgb(0 0 0 / 0.04), 0 18px 40px -18px rgb(0 0 0 / 0.25)",
        glow: "0 0 0 1px rgb(var(--brand) / 0.25), 0 12px 40px -10px rgb(var(--brand) / 0.45)",
      },
      keyframes: {
        drift: {
          "0%,100%": { transform: "translate3d(0,0,0) scale(1)" },
          "33%": { transform: "translate3d(4%, -6%, 0) scale(1.08)" },
          "66%": { transform: "translate3d(-5%, 4%, 0) scale(0.95)" },
        },
        shimmer: { "100%": { transform: "translateX(100%)" } },
        twinkle: { "0%,100%": { opacity: 0.15 }, "50%": { opacity: 0.7 } },
      },
      animation: {
        drift: "drift 22s ease-in-out infinite",
        "drift-slow": "drift 34s ease-in-out infinite reverse",
        shimmer: "shimmer 1.6s infinite",
        twinkle: "twinkle 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
