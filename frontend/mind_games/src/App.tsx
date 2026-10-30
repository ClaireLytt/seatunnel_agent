import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  STYLE_DIMENSIONS,
  STYLE_ITEMS,
  STYLE_LABEL,
  scoreStyle,
  styleVerdict,
} from '@/lib/optimism'
import { STRENGTH_CARDS, STRENGTH_LABEL, type Strength, topStrengths } from '@/lib/strengths'
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

function Bar({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  return (
    <div className="flex items-center gap-3">
      <span className="mg-label w-32 shrink-0 normal-case tracking-[0.1em]">{label}</span>
      <div className="mg-bar flex-1">
        <div className="mg-bar-fill" style={{ width: `${(100 * value) / max}%` }} />
      </div>
      <span className="mg-fade w-10 text-right text-sm">{value}</span>
    </div>
  )
}

function Optimism() {
  const { t } = useTranslation()
  const [picks, setPicks] = useState<boolean[]>(() => load(OPT_KEY, []))
  const [prev, setPrev] = useState<number | null>(() => {
    const hist = load<number[]>(HIST_KEY + '.opt', [])
    return hist.length > 1 ? hist[hist.length - 2] : null
  })
  const done = picks.length >= STYLE_ITEMS.length
  const item = STYLE_ITEMS[picks.length]
  const result = scoreStyle(picks)

  useEffect(() => save(OPT_KEY, picks), [picks])

  // event-driven history: the click that completes the round records it
  const pick = (optimistic: boolean) => {
    setPicks((p) => {
      const next = [...p, optimistic]
      if (next.length === STYLE_ITEMS.length) {
        const hist = load<number[]>(HIST_KEY + '.opt', [])
        setPrev(hist.length ? hist[hist.length - 1] : null)
        save(HIST_KEY + '.opt', [...hist, scoreStyle(next).overall])
      }
      return next
    })
  }

  if (!done && item) {
    return (
      <div className="flex flex-col gap-5">
        <p className="mg-label">
          {t('progress')} {picks.length + 1} / {STYLE_ITEMS.length}
        </p>
        <p className="mg-ink text-lg leading-relaxed">{item.situation}</p>
        <p className="mg-sub text-sm">{t('optimism_hint')}</p>
        <div className="flex flex-col gap-3">
          {item.options.map((o, i) => (
            <button key={i} className="mg-option text-left" onClick={() => pick(o.optimistic)}>
              {o.text}
            </button>
          ))}
        </div>
        {picks.length > 0 && (
          <button className="mg-back self-start" onClick={() => setPicks((p) => p.slice(0, -1))}>
            ‹ {t('back')}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {STYLE_DIMENSIONS.map((d) => {
        const r = result.byDimension[d]
        return <Bar key={d} label={STYLE_LABEL[d].zh} value={r.optimistic} max={r.total || 1} />
      })}
      <p className="mg-ink mt-2 text-base leading-relaxed">
        <span className="mg-label">{t('verdict_label')} · </span>
        {styleVerdict(result.overall)}
      </p>
      {prev !== null && (
        <p className="mg-fade text-sm">{t('last_vs', { a: prev, b: result.overall })}</p>
      )}
      <button className="mg-btn self-start" onClick={() => setPicks([])}>
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
      <div className="flex flex-col gap-5">
        <p className="mg-label">
          {t('progress')} {picks.length + 1} / {STRENGTH_CARDS.length}
        </p>
        <p className="mg-sub text-sm">{t('strengths_hint')}</p>
        <div className="flex flex-col gap-3">
          <button
            className="mg-option text-left"
            onClick={() => setPicks((p) => [...p, card.a.strength])}
          >
            {card.a.text}
          </button>
          <button
            className="mg-option text-left"
            onClick={() => setPicks((p) => [...p, card.b.strength])}
          >
            {card.b.text}
          </button>
        </div>
        {picks.length > 0 && (
          <button className="mg-back self-start" onClick={() => setPicks((p) => p.slice(0, -1))}>
            ‹ {t('back')}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="mg-label">{t('your_top')}</p>
      {top3.map((s, i) => (
        <div key={s.strength} className="mg-card">
          <p className="mg-label normal-case tracking-[0.14em]">
            NO.{i + 1} · {STRENGTH_LABEL[s.strength].zh}
          </p>
          <p className="mg-ink mt-2 text-base leading-relaxed">{STRENGTH_LABEL[s.strength].desc}</p>
        </div>
      ))}
      <button className="mg-btn self-start" onClick={() => setPicks([])}>
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
    <div className="flex flex-col gap-5">
      <p className="mg-sub text-sm">{t('questions_hint')}</p>
      {FIVE_QUESTIONS.map((q) => (
        <div key={q.pillar}>
          <p className="mg-label mb-2">
            {PILLAR_LABEL[q.pillar].letter} · {i18n.language === 'en' ? q.en : q.zh}
          </p>
          <input
            value={answers[q.pillar]}
            onChange={(e) => setAnswers((a) => ({ ...a, [q.pillar]: e.target.value }))}
            placeholder={t('answer_ph')}
            className="mg-input"
          />
        </div>
      ))}
      <button className="mg-btn self-start" disabled={!complete} onClick={() => setRevealed(true)}>
        {t('reveal')}
      </button>
      {revealed && complete && (
        <div className="mt-2 flex flex-col gap-3">
          {PILLARS.map((p) => (
            <Bar
              key={p}
              label={`${PILLAR_LABEL[p].letter} · ${
                i18n.language === 'en' ? PILLAR_LABEL[p].en : PILLAR_LABEL[p].zh
              }`}
              value={scoreAnswer(p, answers[p])}
            />
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
    <div className="mg-shell">
      <div className="mg-fog" aria-hidden="true" />
      <div className="mg-grain" aria-hidden="true" />
      <div className="mg-vignette" aria-hidden="true" />

      <div className="relative mx-auto max-w-[760px] px-4 py-12">
        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="mg-label mb-4">Room 1913 · {t('badge', 'the garden corner')}</p>
            <h1 className="mg-title text-4xl md:text-5xl">{t('title')}</h1>
            <p className="mg-sub mt-4 max-w-[560px] text-base leading-relaxed">{t('subtitle')}</p>
          </div>
          <a href="/" className="mg-home shrink-0">
            {t('home')}
          </a>
        </header>

        <div className="mg-rule mt-8" aria-hidden="true">
          <span className="text-sm">❦</span>
        </div>

        <nav className="mt-6 flex gap-8">
          {tabs.map((x) => (
            <button
              key={x.id}
              onClick={() => setTab(x.id)}
              className={`mg-tab${tab === x.id ? ' mg-tab-active' : ''}`}
            >
              {x.label}
            </button>
          ))}
        </nav>

        <section className="mg-paper mt-6 p-7 md:p-9">
          {tab === 'optimism' && <Optimism />}
          {tab === 'strengths' && <Strengths />}
          {tab === 'questions' && <Questions />}
        </section>
      </div>
    </div>
  )
}
