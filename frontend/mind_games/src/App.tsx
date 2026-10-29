import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '@shared/components/card'
import { PageHeader } from '@shared/components/PageHeader'
import { fieldCls, labelCls } from '@shared/constants'
import {
  STYLE_DIMENSIONS,
  STYLE_ITEMS,
  STYLE_LABEL,
  scoreStyle,
  styleVerdict,
} from '@/lib/optimism'
import {
  STRENGTH_CARDS,
  STRENGTH_LABEL,
  type Strength,
  topStrengths,
} from '@/lib/strengths'
import { FIVE_QUESTIONS, PILLARS, PILLAR_LABEL, type Pillar, scoreAnswer } from '@/lib/perma'

const OPT_KEY = 'st_games.optimism.v1'
const STR_KEY = 'st_games.strengths.v1'
const Q_KEY = 'st_games.questions.v1'
const HIST_KEY = 'st_games.results.v1'

type Tab = 'optimism' | 'strengths' | 'questions'

function load<T>(key: string, fallback: T): T {
  try {
    const v = JSON.parse(localStorage.getItem(key) ?? 'null')
    return (v ?? fallback) as T
  } catch {
    return fallback
  }
}

function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* private mode */
  }
}

const btnCls =
  'rounded border-[1.5px] border-ink px-4 py-2 font-mono text-sm font-semibold ' +
  'text-ink transition hover:-translate-x-px hover:-translate-y-px hover:shadow-hard disabled:opacity-50'
const optionCls =
  'w-full rounded border-[1.5px] border-ink/40 px-4 py-3 text-left text-sm leading-relaxed ' +
  'transition hover:-translate-x-px hover:-translate-y-px hover:border-ink hover:shadow-hard'

function Bar({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 font-mono text-xs text-ink-soft">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded bg-ink/10">
        <div className="h-full bg-ink/70" style={{ width: `${(100 * value) / max}%` }} />
      </div>
      <span className="w-10 text-right font-mono text-xs text-ink-soft">{value}</span>
    </div>
  )
}

function Optimism() {
  const { t } = useTranslation()
  const [picks, setPicks] = useState<boolean[]>(() => load(OPT_KEY, []))
  const [prev, setPrev] = useState<number | null>(null)
  const done = picks.length >= STYLE_ITEMS.length
  const item = STYLE_ITEMS[picks.length]
  const result = scoreStyle(picks)

  useEffect(() => save(OPT_KEY, picks), [picks])
  useEffect(() => {
    if (!done) return
    const hist = load<number[]>(HIST_KEY + '.opt', [])
    if (hist[hist.length - 1] !== result.overall) {
      setPrev(hist.length ? hist[hist.length - 1] : null)
      save(HIST_KEY + '.opt', [...hist, result.overall])
    } else {
      setPrev(hist.length > 1 ? hist[hist.length - 2] : null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done])

  if (!done && item) {
    return (
      <div className="flex flex-col gap-4">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink-soft">
          {t('progress')} {picks.length + 1} / {STYLE_ITEMS.length}
        </p>
        <p className="text-base leading-relaxed">{item.situation}</p>
        <p className="text-sm text-muted">{t('optimism_hint')}</p>
        <div className="flex flex-col gap-2">
          {item.options.map((o, i) => (
            <button key={i} className={optionCls} onClick={() => setPicks((p) => [...p, o.optimistic])}>
              {o.text}
            </button>
          ))}
        </div>
        {picks.length > 0 && (
          <button className="self-start font-mono text-xs text-ink-soft underline"
                  onClick={() => setPicks((p) => p.slice(0, -1))}>
            ‹ {t('back')}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {STYLE_DIMENSIONS.map((d) => {
        const r = result.byDimension[d]
        return <Bar key={d} label={STYLE_LABEL[d].zh} value={r.optimistic} max={r.total || 1} />
      })}
      <p className="mt-2 text-sm leading-relaxed">
        <span className="font-mono text-xs uppercase tracking-[0.18em] text-ink-soft">
          {t('verdict_label')} ·{' '}
        </span>
        {styleVerdict(result.overall)}
      </p>
      {prev !== null && (
        <p className="font-mono text-xs text-ink-soft">
          {t('last_vs', { a: prev, b: result.overall })}
        </p>
      )}
      <button className={`${btnCls} self-start`} onClick={() => setPicks([])}>
        {t('again')}
      </button>
    </div>
  )
}

function Strengths() {
  const { t } = useTranslation()
  const [picks, setPicks] = useState<Strength[]>(() => load(STR_KEY, []))
  const done = picks.length >= STRENGTH_CARDS.length
  const card = STRENGTH_CARDS[picks.length]
  const top3 = topStrengths(picks)

  useEffect(() => save(STR_KEY, picks), [picks])

  if (!done && card) {
    return (
      <div className="flex flex-col gap-4">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink-soft">
          {t('progress')} {picks.length + 1} / {STRENGTH_CARDS.length}
        </p>
        <p className="text-sm text-muted">{t('strengths_hint')}</p>
        <div className="flex flex-col gap-2">
          <button className={optionCls} onClick={() => setPicks((p) => [...p, card.a.strength])}>
            {card.a.text}
          </button>
          <button className={optionCls} onClick={() => setPicks((p) => [...p, card.b.strength])}>
            {card.b.text}
          </button>
        </div>
        {picks.length > 0 && (
          <button className="self-start font-mono text-xs text-ink-soft underline"
                  onClick={() => setPicks((p) => p.slice(0, -1))}>
            ‹ {t('back')}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-ink-soft">{t('your_top')}</p>
      {top3.map((s, i) => (
        <div key={s.strength} className="rounded border-[1.5px] border-ink/30 px-4 py-3">
          <p className="font-mono text-xs text-ink-soft">
            NO.{i + 1} · {STRENGTH_LABEL[s.strength].zh}
          </p>
          <p className="mt-1 text-sm leading-relaxed">{STRENGTH_LABEL[s.strength].desc}</p>
        </div>
      ))}
      <button className={`${btnCls} self-start`} onClick={() => setPicks([])}>
        {t('again')}
      </button>
    </div>
  )
}

function Questions() {
  const { t, i18n } = useTranslation()
  const [answers, setAnswers] = useState<Record<Pillar, string>>(() =>
    load(Q_KEY, Object.fromEntries(PILLARS.map((p) => [p, ''])) as Record<Pillar, string>),
  )
  const [revealed, setRevealed] = useState(false)
  const complete = PILLARS.every((p) => answers[p].trim().length > 0)

  useEffect(() => save(Q_KEY, answers), [answers])

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">{t('questions_hint')}</p>
      {FIVE_QUESTIONS.map((q) => (
        <div key={q.pillar}>
          <label className={labelCls}>
            {PILLAR_LABEL[q.pillar].letter} · {i18n.language === 'en' ? q.en : q.zh}
          </label>
          <input
            value={answers[q.pillar]}
            onChange={(e) => setAnswers((a) => ({ ...a, [q.pillar]: e.target.value }))}
            placeholder={t('answer_ph')}
            className={fieldCls}
          />
        </div>
      ))}
      <button className={`${btnCls} self-start`} disabled={!complete} onClick={() => setRevealed(true)}>
        {t('reveal')}
      </button>
      {revealed && complete && (
        <div className="mt-2 flex flex-col gap-2">
          {PILLARS.map((p) => (
            <Bar key={p}
                 label={`${PILLAR_LABEL[p].letter} · ${i18n.language === 'en' ? PILLAR_LABEL[p].en : PILLAR_LABEL[p].zh}`}
                 value={scoreAnswer(p, answers[p])} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>('optimism')

  const tabs: { id: Tab; label: string }[] = [
    { id: 'optimism', label: t('tab_optimism') },
    { id: 'strengths', label: t('tab_strengths') },
    { id: 'questions', label: t('tab_questions') },
  ]

  return (
    <div className="mx-auto max-w-[860px] px-4 py-8">
      <PageHeader badge="ai / games" titlePrefix="🎲" maxW="max-w-[660px]" />

      <div className="mt-6 flex gap-2">
        {tabs.map((x) => (
          <button
            key={x.id}
            onClick={() => setTab(x.id)}
            className={`rounded border-[1.5px] px-4 py-2 font-mono text-xs font-semibold transition ${
              tab === x.id
                ? 'border-ink bg-ink text-[var(--paper)]'
                : 'border-ink/30 text-ink-soft hover:border-ink'
            }`}
          >
            {x.label}
          </button>
        ))}
      </div>

      <Card className="mt-4">
        {tab === 'optimism' && <Optimism />}
        {tab === 'strengths' && <Strengths />}
        {tab === 'questions' && <Questions />}
      </Card>
    </div>
  )
}
