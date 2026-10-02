import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0a0e14",
        panel: "#121823",
        edge: "#1f2a3a",
        accent: "#38bdf8",
      },
    },
  },
  plugins: [],
};

export default config;
