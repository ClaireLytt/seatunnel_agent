// Client-side CSV export — column structure mirrors the Gradio page's
// _csv_file (agents/ai/llm_cost/ui.py): per-day/per-model cost detail,
// blank row, then the by-model totals block. UTF-8 BOM for Excel.
import type { Summary } from '@/api'

function round6(v: number): number {
  return Math.round(v * 1e6) / 1e6
}

export function summaryCsv(summary: Summary): string | null {
  const byDayModel = summary.by_day_model ?? {}
  const days = Object.keys(byDayModel).sort()
  if (days.length === 0) return null
  const rows: string[][] = [['day', 'model', 'cost_usd']]
  for (const day of days) {
    for (const model of Object.keys(byDayModel[day]).sort()) {
      rows.push([day, model, String(round6(byDayModel[day][model]))])
    }
  }
  rows.push([])
  rows.push(['model', 'calls', 'input', 'output', 'cost_usd'])
  for (const model of Object.keys(summary.by_model ?? {}).sort()) {
    const b = summary.by_model[model]
    rows.push([model, String(b.calls), String(b.input), String(b.output), String(b.cost_usd)])
  }
  const quote = (s: string) => (/[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s)
  return rows.map((r) => r.map(quote).join(',')).join('\r\n') + '\r\n'
}

export function downloadCsv(csv: string, filename = 'llm_cost.csv'): void {
  const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
