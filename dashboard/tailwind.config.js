/** @type {import('tailwindcss').Config} */
// Colors are the dataviz skill's validated reference palette (see
// docs/ for the validation run) — swap values here, not ad hoc in components.
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        surface: {
          light: '#fcfcfb',
          dark: '#1a1a19',
          page: { light: '#f9f9f7', dark: '#0d0d0d' },
        },
        ink: {
          primary: { light: '#0b0b0b', dark: '#ffffff' },
          secondary: { light: '#52514e', dark: '#c3c2b7' },
          muted: '#898781',
        },
        grid: { light: '#e1e0d9', dark: '#2c2c2a' },
        // Sequential (risk magnitude) — single hue, light -> dark.
        risk: {
          100: '#cde2fb', 150: '#b7d3f6', 200: '#9ec5f4', 250: '#86b6ef',
          300: '#6da7ec', 350: '#5598e7', 400: '#3987e5', 450: '#2a78d6',
          500: '#256abf', 550: '#1c5cab', 600: '#184f95', 650: '#104281',
          700: '#0d366b',
        },
        // Categorical slots 1 & 2 — rural vs. suburban/urban comparison.
        series: {
          suburban: { light: '#2a78d6', dark: '#3987e5' },
          rural: { light: '#eb6834', dark: '#d95926' },
        },
        // Status (fixed, never themed) — data-density flag, priority tiers.
        status: {
          good: '#0ca30c',
          warning: '#fab219',
          serious: '#ec835a',
          critical: '#d03b3b',
        },
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
