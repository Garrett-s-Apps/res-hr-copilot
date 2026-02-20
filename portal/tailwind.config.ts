import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: "#1B2A4A",
          50: "#f0f3f8",
          100: "#d9e1ef",
          200: "#b3c3df",
          300: "#7e9ac7",
          400: "#4d72ac",
          500: "#2f5191",
          600: "#243f77",
          700: "#1B2A4A",
          800: "#162240",
          900: "#101a30",
        },
        gold: {
          DEFAULT: "#C9A84C",
          50: "#fdf9ee",
          100: "#f9f0d2",
          200: "#f2dfa1",
          300: "#e8c860",
          400: "#C9A84C",
          500: "#b8923a",
          600: "#9c7730",
          700: "#7e5e29",
          800: "#664c24",
          900: "#533e1f",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
};
export default config;
