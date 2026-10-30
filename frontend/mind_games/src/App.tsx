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
const LEDGER_KEY = 'st_games.optledger.v1'
const THREE_KEY = 'st_games.three.v1'
// shared with the landing page's garden-corner notebook (hub pages.py)
const GARDEN_KEY = 'st_garden.notes.v1'

type Tab = 'optimism' | 'strengths' | 'questions' | 'three'

function today(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`
}

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
        const score = scoreStyle(next).overall
        save(HIST_KEY + '.opt', [...hist, score])
        const ledger = load<{ day: string; score: number }[]>(LEDGER_KEY, [])
        save(LEDGER_KEY, [...ledger, { day: today(), score }])
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
      <Ledger />
    </div>
  )
}

function Ledger() {
  const { t } = useTranslation()
  const entries = load<{ day: string; score: number }[]>(LEDGER_KEY, [])
  if (entries.length < 2) return null
  return (
    <div className="mt-4 border-t border-[rgba(217,154,78,0.16)] pt-4">
      <p className="mg-label mb-3">{t('ledger')}</p>
      <div className="flex flex-col gap-2">
        {entries
          .slice(-8)
          .reverse()
          .map((e, i) => (
            <div key={entries.length - i} className="flex items-center gap-3">
              <span className="mg-label w-28 shrink-0 normal-case tracking-[0.1em]">{e.day}</span>
              <div className="mg-bar flex-1">
                <div className="mg-bar-fill" style={{ width: `${e.score}%` }} />
              </div>
              <span className="mg-fade w-10 text-right text-sm">{e.score}</span>
            </div>
          ))}
      </div>
    </div>
  )
}

type ThreeEntry = { day: string; items: { what: string; why: string }[] }

function streakOf(entries: ThreeEntry[]): number {
  const days = new Set(entries.map((e) => e.day))
  let n = 0
  const d = new Date()
  // tonight counts when written; otherwise the streak ends yesterday
  if (!days.has(today())) d.setDate(d.getDate() - 1)
  for (;;) {
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
      d.getDate(),
    ).padStart(2, '0')}`
    if (!days.has(key)) break
    n += 1
    d.setDate(d.getDate() - 1)
  }
  return n
}

function Lamp({ streak }: { streak: number }) {
  const warmth = Math.min(streak, 7) / 7
  return (
    <svg width="72" height="96" viewBox="0 0 72 96" aria-hidden="true" className="shrink-0">
      {streak > 0 && <circle cx="36" cy="30" r={16 + 14 * warmth} fill="rgba(255,190,110,0.14)" />}
      {streak > 0 && (
        <>
          <circle
            cx="36"
            cy="30"
            r={7 + 5 * warmth}
            fill={`rgba(255,196,120,${0.18 + 0.3 * warmth})`}
          />
          <path
            d="M36 22 C 40 27, 40 32, 36 36 C 32 32, 32 27, 36 22 Z"
            fill={`rgba(255,208,140,${0.55 + 0.4 * warmth})`}
          />
        </>
      )}
      <g stroke="rgba(217,154,78,0.7)" strokeWidth="1.5" fill="none" strokeLinecap="round">
        {/* glass chimney */}
        <path d="M28 44 L 28 22 Q 28 13 36 11 Q 44 13 44 22 L 44 44" />
        {/* burner collar */}
        <path d="M25 44 L 47 44" />
        {/* oil bowl */}
        <path d="M24 48 Q 24 62 36 64 Q 48 62 48 48 Q 42 46 36 46 Q 30 46 24 48 Z" />
        {/* stem and foot */}
        <path d="M36 64 L 36 72" />
        <path d="M24 78 Q 36 71 48 78 Q 36 85 24 78 Z" />
      </g>
    </svg>
  )
}

function ThreeGoodThings() {
  const { t } = useTranslation()
  const [entries, setEntries] = useState<ThreeEntry[]>(() => load(THREE_KEY, []))
  const [drafts, setDrafts] = useState<{ what: string; why: string }[]>([
    { what: '', why: '' },
    { what: '', why: '' },
    { what: '', why: '' },
  ])
  const todayEntry = entries.find((e) => e.day === today())
  const streak = streakOf(entries)
  const complete = drafts.every((d) => d.what.trim().length > 0)
  const cornerNotes = load<{ day: string; text: string }[]>(GARDEN_KEY, [])

  const setDraft = (i: number, field: 'what' | 'why', v: string) =>
    setDrafts((ds) => ds.map((d, j) => (j === i ? { ...d, [field]: v } : d)))

  const setDown = () => {
    const entry: ThreeEntry = {
      day: today(),
      items: drafts.map((d) => ({ what: d.what.trim(), why: d.why.trim() })),
    }
    const next = [...entries, entry]
    setEntries(next)
    save(THREE_KEY, next)
    // the evening also lands in the landing page's garden-corner notebook
    const text = entry.items.map((x) => x.what).join('；')
    save(GARDEN_KEY, [...cornerNotes, { day: entry.day, text }])
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-5">
        <Lamp streak={streak} />
        <div>
          <p className="mg-label">
            {streak > 0 ? t('lamp_streak', { n: streak }) : t('lamp_first')}
          </p>
          <p className="mg-sub mt-2 text-sm leading-relaxed">{t('three_hint')}</p>
        </div>
      </div>

      {todayEntry ? (
        <>
          <p className="mg-ink text-base">{t('today_done')}</p>
          <div className="flex flex-col gap-3">
            {todayEntry.items.map((x, i) => (
              <div key={i} className="mg-card">
                <p className="mg-ink text-base leading-relaxed">{x.what}</p>
                {x.why && <p className="mg-fade mt-1 text-sm italic">{x.why}</p>}
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-col gap-4">
            {drafts.map((d, i) => (
              <div key={i} className="flex flex-col gap-2">
                <p className="mg-label normal-case tracking-[0.14em]">NO.{i + 1}</p>
                <input
                  value={d.what}
                  onChange={(e) => setDraft(i, 'what', e.target.value)}
                  placeholder={t('what_ph')}
                  className="mg-input"
                />
                <input
                  value={d.why}
                  onChange={(e) => setDraft(i, 'why', e.target.value)}
                  placeholder={t('why_ph')}
                  className="mg-input"
                />
              </div>
            ))}
          </div>
          <button className="mg-btn self-start" disabled={!complete} onClick={setDown}>
            {t('save_three')}
          </button>
          <p className="mg-mute text-sm">{t('corner_note')}</p>
        </>
      )}

      {entries.length > (todayEntry ? 1 : 0) && (
        <div className="mt-2 border-t border-[rgba(217,154,78,0.16)] pt-4">
          <p className="mg-label mb-3">{t('recent_evenings')}</p>
          <div className="flex flex-col gap-2">
            {entries
              .filter((e) => e.day !== today())
              .slice(-5)
              .reverse()
              .map((e) => (
                <p key={e.day} className="mg-fade text-sm">
                  <span className="mg-label mr-3 normal-case tracking-[0.1em]">{e.day}</span>
                  {e.items.map((x) => x.what).join('；')}
                </p>
              ))}
          </div>
        </div>
      )}

      {cornerNotes.length > 0 && (
        <div className="border-t border-[rgba(217,154,78,0.16)] pt-4">
          <p className="mg-label mb-3">{t('from_corner')}</p>
          <div className="flex flex-col gap-2">
            {cornerNotes
              .slice(-3)
              .reverse()
              .map((n, i) => (
                <p key={i} className="mg-fade text-sm">
                  <span className="mg-label mr-3 normal-case tracking-[0.1em]">{n.day}</span>
                  {n.text}
                </p>
              ))}
          </div>
        </div>
      )}
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
    { id: 'three', label: t('tab_three') },
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
          {tab === 'three' && <ThreeGoodThings />}
        </section>
      </div>
    </div>
  )
}
