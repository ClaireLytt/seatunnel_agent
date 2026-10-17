import type { Config } from 'tailwindcss'

// Engineering-paper Tailwind preset: maps the CSS variables from
// src/theme.css to utility names. Apps extend via `presets: [preset]`.
export default {
  content: [],
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
} satisfies Config
