/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#050505",
        panel: "#121212",
        accent: "#f45d48",
        accentOrange: "#f78c1f",
        accentGreen: "#22c55e",
        accentRed: "#ef4444",
        accentCyan: "#67f0d6",
        textMuted: "#7f8ea3",
      },
      fontFamily: {
        sans: ["'IBM Plex Sans'", "Inter", "ui-sans-serif", "system-ui"],
      },
    },
  },
  plugins: [],
};
