/** @type {import('tailwindcss').Config} */

// Every colour is a CSS variable (index.css), so one class works in light and dark.
// Palette: paper + ink + one accent (ledger blue). ok / warn / bad are only for verdicts and checks.
const token = name => `rgb(var(--${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Instrument Sans"', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        serif: ['Newsreader', 'ui-serif', 'Georgia', 'serif'],
      },
      colors: {
        canvas: token('canvas'),
        surface: token('surface'),
        subtle: token('subtle'),
        line: token('line'),
        ink: token('ink'),
        'ink-2': token('ink-2'),
        'ink-3': token('ink-3'),
        brand: {
          50: token('brand-50'),
          100: token('brand-100'),
          500: token('brand-500'),
          600: token('brand-600'),
          700: token('brand-700'),
        },
        ok: token('ok'),
        warn: token('warn'),
        bad: token('bad'),
      },
      boxShadow: {
        sheet: '0 1px 0 rgb(var(--line)), 0 1px 3px rgba(23, 32, 43, 0.04)',
        pop: '0 16px 40px -12px rgba(23, 32, 43, 0.28), 0 2px 6px rgba(23, 32, 43, 0.06)',
      },
      keyframes: {
        'fade-in': { from: { opacity: 0 }, to: { opacity: 1 } },
        'pop-in': { from: { opacity: 0, transform: 'translateY(6px) scale(0.98)' }, to: { opacity: 1, transform: 'none' } },
        stamp: { '0%': { opacity: 0, transform: 'scale(1.18) rotate(-4deg)' }, '60%': { opacity: 1, transform: 'scale(0.97) rotate(-4deg)' }, '100%': { opacity: 1, transform: 'scale(1) rotate(-4deg)' } },
        sweep: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(250%)' } },
        flash: { '0%, 100%': { opacity: 0.35 }, '50%': { opacity: 0.8 } },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out',
        'pop-in': 'pop-in 180ms ease-out',
        stamp: 'stamp 420ms cubic-bezier(.2,.8,.2,1) both',
        sweep: 'sweep 1.4s ease-in-out infinite',
        flash: 'flash 1.2s ease-in-out 2',
      },
    },
  },
  plugins: [],
}
