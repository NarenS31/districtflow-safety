/** @type {import('tailwindcss').Config} */
// AfterImpact NC design tokens. Grounded in the subject matter (asphalt,
// signage, engineering precision) rather than a generic SaaS palette —
// see the design token summary in the redesign commit message for the
// full rationale on each choice.
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Asphalt base — dark by default, not a light theme with a
        // dark-mode toggle bolted on.
        asphalt: {
          base: '#14161A',   // page background
          panel: '#1C1F26',  // floating glass panel surface (used with alpha + blur)
          line: '#2A2E37',   // hairline dividers that carry meaning (tier boundaries etc.)
        },
        ink: {
          primary: '#F2F3F5',
          secondary: '#9AA1AC',
          muted: '#676E7A',
        },
        // Risk gradient anchors — the *shape* (quantile breakpoints) is
        // computed at runtime from the real data in MapView.tsx, but the
        // three anchor hues live here so every consumer (map, leaderboard
        // tier badges, score text) draws from one source.
        risk: {
          low: '#2E9E8F',   // deep teal
          mid: '#E85D3D',   // orange-red
          high: '#D93B3B',  // deep red — reserved for genuine outliers (~p99+)
        },
        // The ONE accent outside the risk gradient. Interactive/selected
        // states only — never used to encode risk severity.
        accent: '#F2A73B',
        // A third, distinct semantic: "mind the data quality," not
        // severity and not interactivity. Deliberately a cool neutral so
        // it never gets confused with risk-red or the accent.
        caution: '#8A93A6',
        // Rural vs. suburban/urban in the disparity chart is a categorical
        // comparison, not a risk-magnitude one — reusing the risk gradient
        // there would visually claim "rural = dangerous," which the real
        // finding does NOT support (rural measures LOWER, likely a
        // reporting-density artifact). Two muted, desaturated neutrals,
        // deliberately outside both the risk gradient and the accent.
        cohort: {
          suburban: '#5B8AA6',
          rural: '#A6825B',
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      backdropBlur: {
        panel: '16px',
      },
      keyframes: {
        'slide-in-right': {
          from: { transform: 'translateX(24px)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        'fade-out-strike': {
          from: { opacity: '1' },
          to: { opacity: '0.35' },
        },
        'value-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'slide-in-right': 'slide-in-right 320ms cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-out-strike': 'fade-out-strike 200ms ease-out forwards',
        'value-in': 'value-in 260ms cubic-bezier(0.16, 1, 0.3, 1) forwards',
      },
    },
  },
  plugins: [],
};
