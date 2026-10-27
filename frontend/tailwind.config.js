/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          DEFAULT: 'var(--color-bg-primary)',
          primary: 'var(--color-bg-primary)',
          secondary: 'var(--color-bg-secondary)',
          card: 'var(--color-surface-card)',
          elevated: 'var(--color-surface-elevated)',
          border: 'var(--color-border)',
          borderAccent: 'var(--color-border-accent)',
        },
        darktext: {
          primary: 'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
        },
        brand: {
          DEFAULT: 'var(--color-accent-emerald)',
          emerald: 'var(--color-accent-emerald)',
          emeraldHover: 'var(--color-accent-emerald-hover)',
          turquoise: 'var(--color-accent-turquoise)',
          tealBright: 'var(--color-accent-teal-bright)',
          error: 'var(--color-error)',
          warning: 'var(--color-warning)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
