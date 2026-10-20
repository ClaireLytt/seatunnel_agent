/**
 * SQL dialects supported by the SeaTunnel analysis agents.
 *
 * Pinned to the legacy _DIALECTS tuple used across Gradio pages;
 * React workspaces should import from here instead of duplicating.
 */
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
