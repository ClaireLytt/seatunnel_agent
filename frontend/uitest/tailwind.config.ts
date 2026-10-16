import type { Config } from 'tailwindcss'
import preset from '../shared/tailwind-preset'

export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  presets: [preset],
  content: ['./index.html', './src/**/*.{ts,tsx}', '../shared/src/**/*.{ts,tsx}'],
} satisfies Config
