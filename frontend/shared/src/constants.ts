// ── SQL dialect list (the 7-dialect baseline shared by most workspaces) ──────
export const DIALECTS = [
  'hive',
  'spark',
  'mysql',
  'postgresql',
  'clickhouse',
  'doris',
  'starrocks',
] as const

export type Dialect = (typeof DIALECTS)[number]

// ── Reusable Tailwind class-name constants (engineering-paper theme) ─────────

export const fieldCls =
  'w-full rounded border border-line bg-[var(--paper)] p-2.5 font-mono text-[13px] text-ink outline-none focus:border-ink'

export const textareaCls =
  'w-full resize-y rounded border border-line bg-[var(--paper)] p-3 font-mono text-[13px] text-ink outline-none focus:border-ink'

export const labelCls =
  'mb-2 block font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft'

export const smallBtnCls =
  'rounded border-[1.5px] border-ink px-3 py-1.5 font-mono text-xs font-semibold text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50'
