/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./dashboard.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Blood-bank brand palette (crimson accent).
        blood: {
          50: "#fff1f2",
          100: "#ffe2e4",
          200: "#ffc9ce",
          300: "#ffa2ab",
          400: "#fb6a78",
          500: "#f03e51",
          600: "#d92d3f",
          700: "#b41f30",
          800: "#951d2c",
          900: "#7d1d2b",
        },
        navy: {
          100: "#e8eef7",
          700: "#1b3a63",
          800: "#12294a",
          900: "#0b1c33",
        },
      },
      fontFamily: {
        sans: [
          "Segoe UI",
          "system-ui",
          "-apple-system",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.04)",
        panel: "0 8px 24px rgba(16,24,40,.08)",
        shell: "0 24px 60px rgba(11,28,51,.18)",
      },
    },
  },
  plugins: [],
};
