/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: {
          DEFAULT: "var(--surface)",
          2: "var(--surface-2)",
        },
        border: "var(--border)",
        fg: "var(--fg)",
        muted: "var(--muted)",
        bull: "var(--bull)",
        bear: "var(--bear)",
        neutral: "var(--neutral)",
        warn: "var(--warn)",
        accent: "var(--accent)",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderRadius: {
        panel: "12px",
        btn: "8px",
      },
    },
  },
  plugins: [],
};
