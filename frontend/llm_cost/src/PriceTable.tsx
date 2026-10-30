// Collapsible price-catalog table — mirrors the Gradio page's price
// accordion (_price_table_md in agents/ai/llm_cost/ui.py).
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchPrices } from '@/api'
import type { PricesResponse } from '@/api'

export function PriceTable() {
  const { t } = useTranslation()
  const [resp, setResp] = useState<PricesResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchPrices()
      .then((r) => {
        setResp(r)
        setError('')
      })
      .catch((e) => {
        setResp(null)
        setError(e instanceof Error ? e.message : String(e))
      })
  }, [])

  return (
    <details className="mt-6 rounded border-[1.5px] border-line bg-card px-4 py-3">
      <summary className="cursor-pointer select-none font-mono text-sm text-ink">
        {t('priceAcc')}
      </summary>
      {error ? (
        <p className="mt-3 font-mono text-sm text-ink">{error}</p>
      ) : resp ? (
        <div className="mt-3">
          <p className="font-mono text-xs text-muted">
            {t('priceNote')}
            <code className="rounded bg-[var(--grid)] px-1.5 py-0.5">{resp.override_path}</code>
          </p>
          <table className="mt-3 border-collapse font-mono text-xs">
            <thead>
              <tr>
                {[t('pricePrefix'), t('priceInput'), t('priceOutput'), t('priceSource')].map(
                  (h) => (
                    <th
                      key={h}
                      className="border border-line px-3 py-1.5 text-left font-semibold text-ink"
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {resp.prices.map((p) => (
                <tr key={p.prefix}>
                  <td className="border border-line px-3 py-1.5">
                    <code>{p.prefix}</code>
                  </td>
                  <td className="border border-line px-3 py-1.5">{p.input_usd}</td>
                  <td className="border border-line px-3 py-1.5">{p.output_usd}</td>
                  <td className="border border-line px-3 py-1.5">{p.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </details>
  )
}
