/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f4ff",
          500: "#4f6ef7",
          600: "#3b5de6",
          700: "#2d4dd4",
          900: "#1a2e6e",
        },
      },
    },
  },
  plugins: [],
};
