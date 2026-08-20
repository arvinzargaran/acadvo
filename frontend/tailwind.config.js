/** @type {import('tailwindcss').Config} */

// Wayfinding — the app-wide design system. See the token block in index.css.
//
// Every scale below resolves through CSS custom properties holding *space-
// separated RGB channels* rather than hex. That is what lets Tailwind's opacity
// modifiers work against a themed palette: `bg-dark-900/40` and
// `bg-primary-500/15` compile to `rgb(var(--…) / 0.4)` and stay correct when the
// theme flips. (With hex-valued variables Tailwind emits the colour and
// silently drops the alpha.)
const channel = (name) => ({ opacityValue }) =>
  opacityValue === undefined
    ? `rgb(var(${name}))`
    : `rgb(var(${name}) / ${opacityValue})`;

const ramp = (prefix, steps) =>
  Object.fromEntries(steps.map((s) => [s, channel(`--${prefix}-${s}`)]));

const NEUTRAL_STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
const BRAND_STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        // One family across every role, differentiated by width and weight the
        // way a signage system is. The `wdth` axis is what makes the expanded
        // caps possible without a second typeface.
        sans: ['"Archivo Variable"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Helvetica', 'Arial', 'sans-serif'],
        display: ['"Archivo Variable"', '-apple-system', 'BlinkMacSystemFont', 'Helvetica', 'Arial', 'sans-serif'],
        serif: ['"Archivo Variable"', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', '"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
      },
      colors: {
        // Interactive / brand. Also the "you are here" colour on the network.
        primary: ramp('c-primary', BRAND_STEPS),
        accent: ramp('c-primary', BRAND_STEPS),

        // Signal colours. A transit network already signals in red/amber/green,
        // so danger, warning, and success ride the same three.
        red: ramp('c-signal-red', NEUTRAL_STEPS),
        rose: ramp('c-signal-red', NEUTRAL_STEPS),
        amber: ramp('c-signal-amber', NEUTRAL_STEPS),
        yellow: ramp('c-signal-amber', NEUTRAL_STEPS),
        green: ramp('c-signal-green', NEUTRAL_STEPS),
        emerald: ramp('c-signal-green', NEUTRAL_STEPS),

        // Surfaces and text. The numeric ramp runs light → ink, so `bg-dark-950`
        // is the app background and `text-dark-50` is the primary text colour in
        // both themes.
        dark: ramp('c-dark', NEUTRAL_STEPS),

        paper: {
          DEFAULT: channel('--c-dark-950'),
          card: channel('--c-dark-800'),
        },
        ink: channel('--c-dark-50'),
      },
      borderRadius: {
        // Signage is routed vinyl on a flat plate. Rounded corners are reserved
        // for things that are genuinely round: line bullets, station dots, pills.
        DEFAULT: '0px',
        sm: '0px',
        md: '0px',
        lg: '0px',
        xl: '0px',
        '2xl': '0px',
        '3xl': '0px',
        full: '9999px',
        none: '0px',
      },
      animation: {
        'scale-in': 'scaleIn 0.2s ease-out',
      },
      keyframes: {
        scaleIn: {
          '0%': { transform: 'scale(0.98)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
