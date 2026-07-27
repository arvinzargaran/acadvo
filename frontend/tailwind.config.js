/** @type {import('tailwindcss').Config} */

// Editorial Paper accent — amber-orange #FF8A00
const orange = {
  50: '#FFF4E5',
  100: '#FFE4C2',
  200: '#FFD199',
  300: '#FFB85C',
  400: '#FFA22E',
  500: '#FF8A00',
  600: '#F07E00',
  700: '#C96A00',
  800: '#9E5400',
  900: '#7A4200',
  950: '#4d2900',
};

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        // System grotesque for UI text (no webfont download), editorial serif
        // for headings and the wordmark. Both resolve to native faces.
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', '"Helvetica Neue"', 'Helvetica', 'Arial', 'sans-serif'],
        display: ['"Fraunces Variable"', '"Iowan Old Style"', '"Palatino Linotype"', 'Palatino', 'Georgia', '"Times New Roman"', 'serif'],
        serif: ['"Fraunces Variable"', '"Iowan Old Style"', '"Palatino Linotype"', 'Palatino', 'Georgia', '"Times New Roman"', 'serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        primary: orange,
        accent: orange,
        paper: {
          DEFAULT: 'var(--color-dark-950)',
          card: 'var(--color-dark-800)',
        },
        ink: 'var(--color-dark-50)',
        dark: {
          50: 'var(--color-dark-50)',
          100: 'var(--color-dark-100)',
          200: 'var(--color-dark-200)',
          300: 'var(--color-dark-300)',
          400: 'var(--color-dark-400)',
          500: 'var(--color-dark-500)',
          600: 'var(--color-dark-600)',
          700: 'var(--color-dark-700)',
          800: 'var(--color-dark-800)',
          900: 'var(--color-dark-900)',
          950: 'var(--color-dark-950)',
        },
      },
      animation: {
        'scale-in': 'scaleIn 0.2s ease-out',
      },
      keyframes: {
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
