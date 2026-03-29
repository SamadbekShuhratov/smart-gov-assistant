/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        cloud: "#f8fafc",
        mint: "#7dd3fc",
        coral: "#fb7185",
        sun: "#facc15",
      },
      fontFamily: {
        display: ["'Sora'", "sans-serif"],
        body: ["'Manrope'", "sans-serif"],
      },
      keyframes: {
        floatIn: {
          "0%": { opacity: "0", transform: "translateY(18px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        floatIn: "floatIn 550ms ease-out both",
      },
      boxShadow: {
        soft: "0 12px 40px rgba(15, 23, 42, 0.14)",
      },
    },
  },
  plugins: [],
};
