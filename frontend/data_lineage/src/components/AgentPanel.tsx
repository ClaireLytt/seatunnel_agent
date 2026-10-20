import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { analyzeStream, ApiError, type SourceParams, type SseFrame } from '@/api'
import { ReportView } from '@shared/components/ReportView'
import { fieldCls, labelCls, smallBtnCls } from '@/ui'

// Phase labels for streamed step events (legacy _PHASE_LABELS).
const PHASES: Record<string, Record<string, string>> = {
  en: { thinking: 'Thinking…', executing_tools: 'Executing tools…' },
  zh: { thinking: '思考中…', executing_tools: '执行工具中…' },
}

/** Natural-language lineage Q&A with SSE progress (legacy do_ask). */
export function AgentPanel({
  src,
  onGraph,
}: {
  src: () => SourceParams
  onGraph: (mermaid: string) => void
}) {
  const { t, i18n } = useTranslation()
  const [question, setQuestion] = useState('')
  const [progress, setProgress] = useState('')
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)

  const ask = async () => {
    if (!question.trim()) {
      setAnswer('')
      setProgress(t('need_question'))
      return
    }
    setBusy(true)
    setAnswer('')
    setProgress(t('agent_running'))
    const phases = PHASES[i18n.language.startsWith('zh') ? 'zh' : 'en']
    const lines: string[] = []
    let delta = ''
    const render = () =>
      setProgress([...lines, delta ? delta.trim() + ' ▌' : ''].filter(Boolean).join('\n\n'))
    try {
      await analyzeStream(src(), question.trim(), (f: SseFrame) => {
        if (f.type === 'delta') {
          delta += String(f.text ?? '')
          render()
        } else if (f.type === 'step') {
          delta = ''
          lines.push(
            `⏳ **Step ${f.iteration ?? '?'}/${f.max ?? '?'}** — ${phases[String(f.phase ?? '')] ?? f.phase}`,
          )
          render()
        } else if (f.type === 'tool') {
          const input = (f.input ?? {}) as Record<string, unknown>
          const args = Object.entries(input)
            .map(([k, v]) => `${k}=${JSON.stringify(v).slice(0, 60)}`)
            .join(', ')
          lines.push(args ? `🔧 \`${f.name}\`（${args}）` : `🔧 \`${f.name}\``)
          render()
        } else if (f.type === 'final') {
          setProgress('')
          if (f.error === 'no_settings') setAnswer(t('no_settings'))
          else if (f.error) setAnswer(`❌ ${f.error}`)
          else {
            setAnswer(String(f.answer ?? ''))
            const mermaid = String(f.mermaid ?? '')
            if (mermaid) onGraph(mermaid)
          }
        }
      })
    } catch (e) {
      setProgress('')
      setAnswer(e instanceof ApiError && e.code === 'need_graph'
        ? t('need_graph')
        : String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <details>
        <summary className="cursor-pointer select-none font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
          {t('agent_acc')}
        </summary>
        <div className="mt-3">
          <label className={labelCls}>{t('ask_label')}</label>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={t('ask_ph')}
            rows={2}
            spellCheck={false}
            className={fieldCls}
          />
          <button onClick={ask} disabled={busy} className={`${smallBtnCls} mt-2`}>
            {t('ask_btn')}
          </button>
          {progress && (
            <div className="mt-3 whitespace-pre-wrap text-sm text-muted">{progress}</div>
          )}
          {answer && (
            <div className="mt-3">
              <ReportView markdown={answer} />
            </div>
          )}
        </div>
      </details>
    </Card>
  )
}
