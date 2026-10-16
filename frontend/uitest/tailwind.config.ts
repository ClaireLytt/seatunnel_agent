import type { Config } from 'tailwindcss'

// Theme tokens mirror docs/landing.html (engineering-paper style).
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{ts,tsx}', '../shared/src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: 'var(--paper)',
        ink: 'var(--ink)',
        'ink-soft': 'var(--ink-soft)',
        fg: 'var(--fg)',
        muted: 'var(--muted)',
        card: 'var(--card)',
        line: 'var(--line)',
        accent: 'var(--accent)',
        ok: 'var(--ok)',
      },
      fontFamily: {
        sans: ['Noto Sans SC', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        display: ['Space Grotesk', 'Noto Sans SC', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '3px',
      },
      boxShadow: {
        hard: '3px 3px 0 var(--grid-bold)',
      },
    },
  },
  plugins: [],
} satisfies Config
