import type { Config } from 'tailwindcss'
import preset from './tailwind-preset'

// content globs are resolved relative to the workspace cwd (tailwind default),
// so the same list works for every leaf workspace.
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  presets: [preset],
  content: ['./index.html', './src/**/*.{ts,tsx}', '../shared/src/**/*.{ts,tsx}'],
} satisfies Config
