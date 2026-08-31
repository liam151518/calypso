import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#ff2d75",
          muted: "#ff77a6",
          accent: "#22d3ee",
          ink: "#0a0a14",
          surface: "#13131f",
          border: "#27273a",
        },
      },
      fontFamily: {
        display: ["ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
