"use client";
import { useEffect, useRef, useState } from "react";
import SessionRail from "../components/SessionRail";
import WindowDateChip from "../components/WindowDateChip";
import {
  FIVE_QUESTIONS,
  PILLARS,
  PILLAR_LABEL,
  Pillar,
  GoodNews,
  scoreAnswer,
  todayKey,
} from "../lib/perma";
import {
  GoodThing,
  GoodThingsEntry,
  loadGoodThings,
  saveEntry,
  todayEntry,
  streakOf,
} from "../lib/goodthings";
import {
  STYLE_DIMENSIONS,
  STYLE_ITEMS,
  STYLE_LABEL,
  scoreStyle,
  styleVerdict,
} from "../lib/optimism";
import {
  Strength,
  STRENGTH_CARDS,
  STRENGTH_LABEL,
  topStrengths,
} from "../lib/strengths";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

function Calendar({ history }: { history: GoodNews[] }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth()); // 0-based
  const [picked, setPicked] = useState<GoodNews | null>(null);

  const byDay = new Map<string, GoodNews>();
  for (const n of history) byDay.set(n.day, n);

  const first = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const lead = (first.getDay() + 6) % 7; // Monday-first
  const cells: (number | null)[] = [
    ...Array.from({ length: lead }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  const key = (d: number) =>
    `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

  const shift = (delta: number) => {
    const m = new Date(year, month + delta, 1);
    setYear(m.getFullYear());
    setMonth(m.getMonth());
    setPicked(null);
  };

  return (
    <div className="garden-cal">
      <div className="garden-cal-head">
        <button className="garden-cal-nav font-type" onClick={() => shift(-1)}>‹</button>
        <span className="garden-cal-title font-type">{year} · {month + 1}月</span>
        <button className="garden-cal-nav font-type" onClick={() => shift(1)}>›</button>
      </div>
      <div className="garden-cal-grid">
        {WEEKDAYS.map(w => (
          <span key={w} className="garden-cal-weekday font-type">{w}</span>
        ))}
        {cells.map((d, i) => {
          if (d === null) return <span key={`x${i}`} />;
          const note = byDay.get(key(d));
          return (
            <button
              key={d}
              className={`garden-cal-day font-type ${note ? "garden-cal-day-bloom" : ""} ${picked && note === picked ? "garden-cal-day-on" : ""}`}
              style={note ? { color: PILLAR_COLOR[note.pillar] } : undefined}
              onClick={() => note && setPicked(picked === note ? null : note)}
              disabled={!note}
              aria-label={note ? `${key(d)} · ${PILLAR_LABEL[note.pillar].zh}的好消息` : undefined}
            >
              {note ? "✻" : d}
            </button>
          );
        })}
      </div>
      {picked && (
        <div className="garden-card" style={{ marginTop: "12px" }}>
          <p className="garden-card-tag font-type">
            {picked.day} · {PILLAR_LABEL[picked.pillar].letter} {PILLAR_LABEL[picked.pillar].zh}
          </p>
          <p className="garden-card-text font-serif">“{picked.text}”</p>
        </div>
      )}
    </div>
  );
}

const PILLAR_COLOR: Record<Pillar, string> = {
  positive: "#d99a4e",
  engagement: "#c9b36a",
  relationships: "#9fb88a",
  meaning: "#b87a4a",
  accomplishment: "#e0cfa8",
};

function Flower({ pillar, i }: { pillar: Pillar; i: number }) {
  const color = PILLAR_COLOR[pillar];
  const h = 34 + ((i * 7) % 18); // uneven heights, like a real bed
  const sway = (i % 5) - 2;
  return (
    <svg
      className="garden-flower"
      viewBox="0 0 24 60"
      style={{ height: `${h + 22}px` }}
      aria-label={PILLAR_LABEL[pillar].zh}
    >
      <path
        d={`M12 58 Q ${12 + sway} ${58 - h / 2} 12 ${58 - h}`}
        stroke="rgba(159,184,138,0.55)"
        strokeWidth="1.4"
        fill="none"
      />
      <g transform={`translate(12 ${58 - h})`}>
        {[0, 72, 144, 216, 288].map(a => (
          <ellipse
            key={a}
            cx="0"
            cy="-4.4"
            rx="2.6"
            ry="4.4"
            fill={color}
            opacity="0.82"
            transform={`rotate(${a + sway * 4})`}
          />
        ))}
        <circle r="2.2" fill="rgba(26,20,14,0.9)" stroke={color} strokeWidth="0.8" />
      </g>
    </svg>
  );
}

function Lamp({ streak }: { streak: number }) {
  // the longer the streak, the brighter the lamp burns
  const glow = Math.min(1, 0.25 + streak * 0.12);
  return (
    <span className="garden-lamp" aria-label={`连续 ${streak} 天`}>
      <svg viewBox="0 0 24 34" style={{ filter: `drop-shadow(0 0 ${4 + streak * 2}px rgba(217,154,78,${glow}))` }}>
        <path d="M8 20h8l-1.5 10h-5Z" fill="none" stroke="rgba(217,154,78,0.6)" strokeWidth="1.2" />
        <path
          d="M12 6 C 15 10, 15.5 13, 12 17 C 8.5 13, 9 10, 12 6 Z"
          fill={`rgba(217,154,78,${glow})`}
          stroke="rgba(232,220,196,0.5)"
          strokeWidth="0.6"
        />
      </svg>
      <span className="garden-lamp-count font-type">{streak}</span>
    </span>
  );
}

import Breathing from "../components/Breathing";
import { packSuitcase, unpackSuitcase, suitcaseFilename } from "../lib/porter";
import { loadFlowLog } from "../lib/flow";
import { downloadMonthCard } from "../lib/monthcard";

const CLIENT_KEY = "room1913.garden.client.v1";
const ANSWERS_KEY = "room1913.garden.answers.v1";
const OPTIMISM_KEY = "room1913.garden.optimism.v1";
const STRENGTHS_KEY = "room1913.garden.strengths.v1";
const LAMPSEEN_KEY = "room1913.garden.lampseen.v1";
const GREETED_KEY = "room1913.garden.greeted.v1";
const REPLYSEEN_KEY = "room1913.garden.replyseen.v1";
const CAPSEEN_KEY = "room1913.garden.capseen.v1";
const RESULTS_KEY = "room1913.garden.results.v1";

const NAV = [
  { id: "week", zh: "本周" },
  { id: "news", zh: "好消息" },
  { id: "breath", zh: "呼吸" },
  { id: "things", zh: "三件好事" },
  { id: "optimism", zh: "乐观" },
  { id: "strengths", zh: "优势" },
  { id: "questions", zh: "五问" },
  { id: "bottle", zh: "瓶中信" },
  { id: "capsule", zh: "时间胶囊" },
  { id: "suitcase", zh: "搬家" },
];

function getClientId(): string {
  try {
    let id = localStorage.getItem(CLIENT_KEY);
    if (!id) {
      id = `v-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(CLIENT_KEY, id);
    }
    return id;
  } catch {
    return "anonymous";
  }
}

function PastNights({
  entries,
  open,
  toggle,
}: {
  entries: GoodThingsEntry[];
  open: boolean;
  toggle: () => void;
}) {
  if (!entries.length) return null;
  return (
    <div className="garden-past">
      <button className="garden-game-back font-type" onClick={toggle}>
        {open ? "‹ 收起往夜的记录" : `往夜的记录 · ${entries.length} 晚 ›`}
      </button>
      {open && (
        <ul className="garden-past-list">
          {entries.map(e => (
            <li key={e.day} className="garden-card">
              <p className="garden-card-tag font-type">{e.day}</p>
              {e.items.map((t, i) => (
                <p key={i} className="garden-past-line font-serif">
                  {t.text}
                  {t.why ? <span className="ink-fade"> —— {t.why}</span> : null}
                </p>
              ))}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Garden() {
  // --- five questions ---
  const [answers, setAnswers] = useState<Record<Pillar, string>>(
    () => Object.fromEntries(PILLARS.map(p => [p, ""])) as Record<Pillar, string>
  );
  const [revealed, setRevealed] = useState(false);

  // --- daily good news ---
  const [clientId, setClientId] = useState("");
  const [note, setNote] = useState("");
  const [mine, setMine] = useState<GoodNews | null>(null);
  const [match, setMatch] = useState<GoodNews | null>(null);
  const [history, setHistory] = useState<GoodNews[]>([]);
  const [busy, setBusy] = useState(false);

  // --- lamp back ---
  const [matchLit, setMatchLit] = useState(false);

  // --- optimism game ---
  const [picks, setPicksState] = useState<boolean[]>([]);
  const setPicks = (updater: (prev: boolean[]) => boolean[]) =>
    setPicksState(prev => {
      const next = updater(prev);
      try { localStorage.setItem(OPTIMISM_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  const gameDone = picks.length >= STYLE_ITEMS.length;
  const current = STYLE_ITEMS[picks.length];
  const result = scoreStyle(picks);

  // --- character strengths ---
  const [strengthPicks, setStrengthPicksState] = useState<Strength[]>([]);
  const setStrengthPicks = (updater: (prev: Strength[]) => Strength[]) =>
    setStrengthPicksState(prev => {
      const next = updater(prev);
      try { localStorage.setItem(STRENGTHS_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  const strengthsDone = strengthPicks.length >= STRENGTH_CARDS.length;
  const strengthCard = STRENGTH_CARDS[strengthPicks.length];
  const top3 = topStrengths(strengthPicks);

  // --- retake history: remember each completed run, compare with the last ---
  const [results, setResults] = useState<{
    optimism: { at: number; overall: number }[];
    strengths: { at: number; top: Strength[] }[];
  }>({ optimism: [], strengths: [] });
  const recordedRun = useRef({ optimism: false, strengths: false });

  useEffect(() => {
    try {
      const v = JSON.parse(localStorage.getItem(RESULTS_KEY) ?? "{}");
      setResults({
        optimism: Array.isArray(v.optimism) ? v.optimism : [],
        strengths: Array.isArray(v.strengths) ? v.strengths : [],
      });
    } catch {}
  }, []);

  useEffect(() => {
    if (gameDone && !recordedRun.current.optimism) {
      recordedRun.current.optimism = true;
      setResults(prev => {
        const next = { ...prev, optimism: [...prev.optimism, { at: Date.now(), overall: result.overall }] };
        try { localStorage.setItem(RESULTS_KEY, JSON.stringify(next)); } catch {}
        return next;
      });
    }
    if (!gameDone) recordedRun.current.optimism = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameDone]);

  useEffect(() => {
    if (strengthsDone && !recordedRun.current.strengths) {
      recordedRun.current.strengths = true;
      const top = top3.map(t => t.strength);
      setResults(prev => {
        const next = { ...prev, strengths: [...prev.strengths, { at: Date.now(), top }] };
        try { localStorage.setItem(RESULTS_KEY, JSON.stringify(next)); } catch {}
        return next;
      });
    }
    if (!strengthsDone) recordedRun.current.strengths = false;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strengthsDone]);

  const prevOptimism = results.optimism.length >= 2 ? results.optimism[results.optimism.length - 2] : null;
  const prevStrengths = results.strengths.length >= 2 ? results.strengths[results.strengths.length - 2] : null;

  // --- bottle post ---
  const [bottleText, setBottleText] = useState("");
  const [bottleReceived, setBottleReceived] = useState<string | null>(null);
  const [bottleBusy, setBottleBusy] = useState(false);

  // --- suitcase ---
  const [portNote, setPortNote] = useState("");
  const exportSuitcase = () => {
    try {
      const blob = new Blob([JSON.stringify(packSuitcase(), null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = suitcaseFilename();
      a.click();
      URL.revokeObjectURL(a.href);
      setPortNote("已打包带走。");
    } catch {
      setPortNote("打包失败。");
    }
  };
  const importSuitcase = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        setPortNote(unpackSuitcase(String(reader.result)));
        setTimeout(() => window.location.reload(), 900);
      } catch {
        setPortNote("这不是 1913 号房间的行李。");
      }
    };
    reader.readAsText(file);
  };

  // --- time capsule ---
  interface CapsuleView {
    id: string; createdAt: number; openAt: number; sealed: boolean; text?: string;
  }
  const [capsules, setCapsules] = useState<CapsuleView[]>([]);
  const [capsuleText, setCapsuleText] = useState("");
  const [capsuleDays, setCapsuleDays] = useState(90);
  const [capsuleBusy, setCapsuleBusy] = useState(false);

  const sealCapsule = async () => {
    const text = capsuleText.trim();
    if (!text || capsuleBusy) return;
    setCapsuleBusy(true);
    try {
      const res = await fetch("/api/capsule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, clientId, days: capsuleDays }),
      });
      const d = await res.json();
      if (d.sealed) {
        setCapsules(prev => [...prev, d.sealed].sort((a, b) => a.openAt - b.openAt));
        setCapsuleText("");
      }
    } catch {}
    setCapsuleBusy(false);
  };

  // --- three good things ---
  const [things, setThings] = useState<GoodThing[]>(
    () => [0, 1, 2].map(() => ({ text: "", why: "" }))
  );
  const [entries, setEntries] = useState<GoodThingsEntry[]>([]);
  const savedToday = todayEntry(entries);
  const streak = streakOf(entries);
  const pastEntries = entries
    .filter(e => e !== savedToday)
    .sort((a, b) => b.createdAt - a.createdAt);
  const [showPast, setShowPast] = useState(false);

  // --- lamp echo ---
  const [lampEcho, setLampEcho] = useState(0);
  const [flowWeek, setFlowWeek] = useState({ count: 0, min: 0 });

  // --- reply to the exchanged note ---
  const [replyText, setReplyText] = useState("");
  const [replySent, setReplySent] = useState(false);
  const [replyEcho, setReplyEcho] = useState(0);

  // --- tonight across all visitors + capsule knock ---
  const [tonight, setTonight] = useState<{ count: number; topPillar: Pillar | null } | null>(null);
  const [capsuleKnock, setCapsuleKnock] = useState(false);

  // --- presence + first-visit greeting ---
  const [others, setOthers] = useState(0);
  const [greeting, setGreeting] = useState(false);

  useEffect(() => {
    const id = getClientId();
    setClientId(id);
    try {
      const saved = localStorage.getItem(ANSWERS_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        setAnswers(prev => ({ ...prev, ...parsed }));
      }
    } catch {}
    setEntries(loadGoodThings());
    try {
      const since = Date.now() - 7 * 24 * 60 * 60 * 1000;
      let count = 0, min = 0;
      for (const f of loadFlowLog()) {
        if (f.createdAt >= since) { count++; min += f.actualMin; }
      }
      setFlowWeek({ count, min });
    } catch {}
    try {
      const op = JSON.parse(localStorage.getItem(OPTIMISM_KEY) ?? "[]");
      if (Array.isArray(op)) setPicksState(op.filter(v => typeof v === "boolean"));
      const st = JSON.parse(localStorage.getItem(STRENGTHS_KEY) ?? "[]");
      if (Array.isArray(st)) setStrengthPicksState(st);
    } catch {}
    fetch(`/api/goodnews?clientId=${encodeURIComponent(id)}`)
      .then(r => r.json())
      .then(d => {
        if (d.mine) { setMine(d.mine); setMatch(d.match ?? null); }
        if (d.tonight) setTonight(d.tonight);
        if (Array.isArray(d.history)) {
          setHistory(d.history);
          const lit = d.history.reduce(
            (n: number, g: GoodNews) => n + (g.litBy?.length ?? 0), 0
          );
          const replied = d.history.reduce(
            (n: number, g: GoodNews) => n + (g.replies?.length ?? 0), 0
          );
          try {
            const seen = Number(localStorage.getItem(LAMPSEEN_KEY) ?? "0");
            if (lit > seen) setLampEcho(lit - seen);
            localStorage.setItem(LAMPSEEN_KEY, String(lit));
            const rseen = Number(localStorage.getItem(REPLYSEEN_KEY) ?? "0");
            if (replied > rseen) setReplyEcho(replied - rseen);
            localStorage.setItem(REPLYSEEN_KEY, String(replied));
          } catch {}
        }
      })
      .catch(() => {});
    fetch(`/api/capsule?clientId=${encodeURIComponent(id)}`)
      .then(r => r.json())
      .then(d => {
        if (Array.isArray(d.capsules)) {
          setCapsules(d.capsules);
          const open = d.capsules.filter((c: { sealed: boolean }) => !c.sealed).length;
          try {
            const seen = Number(localStorage.getItem(CAPSEEN_KEY) ?? "0");
            if (open > seen) setCapsuleKnock(true);
            localStorage.setItem(CAPSEEN_KEY, String(open));
          } catch {}
        }
      })
      .catch(() => {});
    try {
      if (!localStorage.getItem(GREETED_KEY)) setGreeting(true);
    } catch {}
    const beat = () =>
      fetch("/api/presence", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clientId: id }),
      })
        .then(r => r.json())
        .then(d => setOthers(Number(d.others) || 0))
        .catch(() => {});
    beat();
    const t = setInterval(beat, 60_000);
    return () => clearInterval(t);
  }, []);

  const dismissGreeting = () => {
    setGreeting(false);
    try { localStorage.setItem(GREETED_KEY, "1"); } catch {}
  };

  // --- anniversary: a note from a month (or a week) ago resurfaces ---
  const anniversary = (() => {
    const fmt = (dt: Date) => todayKey(dt);
    const monthAgo = new Date(); monthAgo.setMonth(monthAgo.getMonth() - 1);
    const weekAgo = new Date(); weekAgo.setDate(weekAgo.getDate() - 7);
    for (const [day, label] of [
      [fmt(monthAgo), "一个月前的今天"],
      [fmt(weekAgo), "一周前的今天"],
    ] as const) {
      const note = history.find(n => n.day === day);
      if (note) return { label, text: note.text };
      const entry = entries.find(e => e.day === day);
      if (entry) return { label, text: entry.items[0]?.text ?? "" };
    }
    return null;
  })();

  // --- this week, in one quiet card ---
  const week = (() => {
    const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
    const since = Date.now() - WEEK_MS;
    const news = history.filter(n => n.createdAt >= since);
    const nights = entries.filter(e => e.createdAt >= since).length;
    const { count: flowCount, min: flowMin } = flowWeek;
    return { news, nights, flowCount, flowMin };
  })();
  const weekHasAnything =
    week.news.length > 0 || week.nights > 0 || week.flowCount > 0;

  const setThing = (i: number, field: keyof GoodThing, v: string) => {
    setThings(prev => prev.map((t, j) => (j === i ? { ...t, [field]: v } : t)));
  };
  const thingsComplete = things.every(t => t.text.trim().length > 0);

  const lightLamp = async () => {
    if (!match || matchLit) return;
    setMatchLit(true); // the gesture lands immediately; server call follows
    try {
      await fetch("/api/goodnews/lamp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: match.id, clientId }),
      });
    } catch {}
  };
  const lampsReceived = history.reduce((n, g) => n + (g.litBy?.length ?? 0), 0);
  const repliesReceived = history.flatMap(g => g.replies ?? []);

  const sendReply = async () => {
    const text = replyText.trim();
    if (!match || !text || replySent) return;
    setReplySent(true);
    try {
      await fetch("/api/goodnews/reply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: match.id, clientId, text }),
      });
    } catch {}
  };

  const castBottle = async () => {
    const text = bottleText.trim();
    if (!text || bottleBusy) return;
    setBottleBusy(true);
    try {
      const res = await fetch("/api/bottle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, clientId }),
      });
      const d = await res.json();
      if (d.cast) {
        setBottleReceived(d.received?.text ?? null);
        setBottleText("");
      }
    } catch {}
    setBottleBusy(false);
  };
  const saveThings = () => {
    if (!thingsComplete) return;
    setEntries(saveEntry(things.map(t => ({ text: t.text.trim(), why: t.why.trim() }))));
  };

  const setAnswer = (p: Pillar, v: string) => {
    setAnswers(prev => {
      const next = { ...prev, [p]: v };
      try { localStorage.setItem(ANSWERS_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  };

  const answeredAll = PILLARS.every(p => answers[p].trim().length > 0);
  const scores = Object.fromEntries(
    PILLARS.map(p => [p, scoreAnswer(p, answers[p])])
  ) as Record<Pillar, number>;

  const share = async () => {
    const text = note.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/goodnews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, clientId }),
      });
      const d = await res.json();
      if (d.mine) {
        setMine(d.mine);
        setMatch(d.match ?? null);
        setNote("");
        if (!d.already) setHistory(prev => [...prev, d.mine]);
      }
    } catch {}
    setBusy(false);
  };

  return (
    <main className="archive-shell">
      <SessionRail active="garden" />

      <section className="archive-stage">
        <header className="archive-stage-head">
          <h1 className="archive-stage-title font-serif">GARDEN</h1>
          <p className="archive-stage-sub font-serif ink-fade">
            五个问题认识自己，一条好消息交换陌生的善意
          </p>
          {others > 0 && (
            <p className="garden-presence font-serif ink-fade">
              今晚花园里还有 {others} 位访客。
            </p>
          )}
          {tonight && tonight.count > 1 && tonight.topPillar && (
            <p className="garden-presence font-serif ink-fade">
              今晚全体访客共种下 {tonight.count} 朵，开得最多的是{PILLAR_LABEL[tonight.topPillar].zh}。
            </p>
          )}
          {capsuleKnock && (
            <p className="garden-echo font-serif">
              <a href="#capsule" className="garden-knock">有一封给你的信到期了，可以拆了。</a>
            </p>
          )}
          <nav className="garden-nav" aria-label="garden sections">
            {NAV.map(n => (
              <a key={n.id} href={`#${n.id}`} className="garden-nav-item font-type">
                {n.zh}
              </a>
            ))}
          </nav>
          {lampEcho > 0 && (
            <p className="garden-echo font-serif">
              你不在的时候，有人为你的好消息点亮了 {lampEcho} 盏灯。
            </p>
          )}
          {replyEcho > 0 && (
            <p className="garden-echo font-serif">
              有人给你的好消息回了一句话。
            </p>
          )}
          {anniversary && anniversary.text && (
            <p className="garden-echo garden-echo-anniv font-serif">
              {anniversary.label}，你写下过：“{anniversary.text}”
            </p>
          )}
        </header>

        {/* ----- this week ----- */}
        {weekHasAnything && (
          <section className="garden-block" id="week">
            <h2 className="garden-block-title font-type">THIS WEEK · 本周小结</h2>
            <ul className="garden-week">
              {week.news.length > 0 && (
                <li className="garden-week-row font-serif">
                  花坛多开了 {week.news.length} 朵
                  <span className="garden-week-dots">
                    {week.news.map(n => (
                      <span
                        key={n.id}
                        className="garden-week-dot"
                        style={{ background: PILLAR_COLOR[n.pillar] }}
                        title={PILLAR_LABEL[n.pillar].zh}
                      />
                    ))}
                  </span>
                </li>
              )}
              {week.nights > 0 && (
                <li className="garden-week-row font-serif">
                  记下了 {week.nights} 晚的三件好事
                  {streak > 1 ? `，油灯连续亮了 ${streak} 天` : ""}
                </li>
              )}
              {week.flowCount > 0 && (
                <li className="garden-week-row font-serif">
                  把表交给雨声 {week.flowCount} 次，共 {week.flowMin} 分钟
                </li>
              )}
              {lampsReceived > 0 && (
                <li className="garden-week-row font-serif">
                  你的好消息照亮过 {lampsReceived} 位访客
                </li>
              )}
            </ul>
          </section>
        )}

        {/* ----- daily good news ----- */}
        <section className="garden-block" id="news">
          <h2 className="garden-block-title font-type">TODAY&apos;S GOOD NEWS · 今日好消息</h2>

          {mine ? (
            <div className="garden-exchange">
              <div className="garden-card garden-card-mine">
                <p className="garden-card-tag font-type">
                  YOURS · {PILLAR_LABEL[mine.pillar].letter} {PILLAR_LABEL[mine.pillar].zh}
                </p>
                <p className="garden-card-text font-serif">“{mine.text}”</p>
                {lampsReceived > 0 && (
                  <p className="garden-hint font-serif ink-fade">
                    你的好消息照亮过 {lampsReceived} 位访客。
                  </p>
                )}
                {repliesReceived.map((r, i) => (
                  <p key={i} className="garden-reply-line font-serif">
                    有人留下一句：“{r.text}”
                  </p>
                ))}
              </div>
              {match ? (
                <div className="garden-card garden-card-match">
                  <p className="garden-card-tag font-type">
                    IN EXCHANGE · 来自另一位访客
                  </p>
                  <p className="garden-card-text font-serif">“{match.text}”</p>
                  <button
                    className={`garden-lamp-btn font-type ${matchLit ? "garden-lamp-btn-lit" : ""}`}
                    onClick={lightLamp}
                    disabled={matchLit}
                  >
                    {matchLit ? "灯已点亮 · 对方会看到" : "点一盏灯回赠"}
                  </button>
                  {replySent ? (
                    <p className="garden-hint font-serif ink-fade">
                      回信已放在对方门口。
                    </p>
                  ) : (
                    <div className="garden-reply-row">
                      <input
                        className="garden-input font-serif"
                        value={replyText}
                        onChange={e => setReplyText(e.target.value)}
                        maxLength={100}
                        placeholder="也可以回一句话……"
                      />
                      <button
                        className="garden-lamp-btn font-type"
                        onClick={sendReply}
                        disabled={!replyText.trim()}
                      >
                        送出
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <p className="garden-hint font-serif italic ink-mute">
                  还没有同类的好消息经过，花园会替你留意。
                </p>
              )}
              <p className="garden-hint font-serif ink-fade">
                今天的好消息已放进花园，明天再来交换一条。
              </p>
            </div>
          ) : (
            <div className="garden-share">
              <textarea
                className="garden-input font-serif"
                value={note}
                onChange={e => setNote(e.target.value)}
                maxLength={280}
                rows={3}
                placeholder="写下今天一件很小的好事……"
              />
              <button
                className="garden-btn font-type"
                onClick={share}
                disabled={!note.trim() || busy}
              >
                {busy ? "SENDING…" : "SHARE · 放进花园"}
              </button>
            </div>
          )}
          {history.length > 0 && (
            <div className="garden-bed">
              <div className="garden-bed-row">
                {history.map((n, i) => (
                  <Flower key={n.id} pillar={n.pillar} i={i} />
                ))}
              </div>
              <div className="garden-bed-ground" />
              <p className="garden-hint font-serif ink-fade">
                你的花坛 · 每一朵都是一条分享过的好消息
              </p>
              <Calendar history={history} />
              <button
                className="garden-game-back font-type"
                onClick={() => downloadMonthCard(history, entries, streak)}
              >
                把这个月装进一张卡片 ›
              </button>
            </div>
          )}
        </section>

        {/* ----- breathing ----- */}
        <section className="garden-block" id="breath">
          <h2 className="garden-block-title font-type">BREATHING · 呼吸窗</h2>
          <p className="garden-hint font-serif ink-fade" style={{ margin: "0 0 14px" }}>
            4-7-8：吸气四拍，屏息七拍，呼气八拍。让房间暗下来，只剩雨声和一圈灯光。
          </p>
          <Breathing
            onFinish={() =>
              document.getElementById("news")?.scrollIntoView({ behavior: "smooth" })
            }
          />
        </section>

        {/* ----- three good things ----- */}
        <section className="garden-block" id="things">
          <h2 className="garden-block-title font-type">
            THREE GOOD THINGS · 今晚的三件好事
            <Lamp streak={streak} />
          </h2>

          {savedToday ? (
            <div className="garden-exchange">
              <ul className="garden-things-done">
                {savedToday.items.map((t, i) => (
                  <li key={i} className="garden-card">
                    <p className="garden-card-tag font-type">NO. {i + 1}</p>
                    <p className="garden-card-text font-serif">{t.text}</p>
                    {t.why && (
                      <p className="garden-things-why font-serif ink-fade">为什么会发生：{t.why}</p>
                    )}
                  </li>
                ))}
              </ul>
              <p className="garden-hint font-serif ink-fade">
                已记下，油灯为你亮着——连续 {streak} 天。
              </p>
              <PastNights entries={pastEntries} open={showPast} toggle={() => setShowPast(v => !v)} />
            </div>
          ) : (
            <div className="garden-share">
              <p className="garden-hint font-serif ink-fade" style={{ margin: "0 0 14px" }}>
                睡前写下今天的三件好事，以及它们为什么会发生。
              </p>
              <ul className="garden-things-list">
                {things.map((t, i) => (
                  <li key={i} className="garden-things-item">
                    <span className="garden-q-letter font-type">{i + 1}</span>
                    <div className="garden-things-fields">
                      <input
                        className="garden-input font-serif"
                        value={t.text}
                        onChange={e => setThing(i, "text", e.target.value)}
                        placeholder="发生了什么好事"
                      />
                      <input
                        className="garden-input font-serif garden-things-why-input"
                        value={t.why}
                        onChange={e => setThing(i, "why", e.target.value)}
                        placeholder="它为什么会发生（可留空）"
                      />
                    </div>
                  </li>
                ))}
              </ul>
              <button
                className="garden-btn font-type"
                onClick={saveThings}
                disabled={!thingsComplete}
              >
                KEEP · 记下这三件
              </button>
              <PastNights entries={pastEntries} open={showPast} toggle={() => setShowPast(v => !v)} />
            </div>
          )}
        </section>

        {/* ----- optimism game ----- */}
        <section className="garden-block" id="optimism">
          <h2 className="garden-block-title font-type">LEARNED OPTIMISM · 乐观解释风格</h2>

          {!gameDone && current ? (
            <div className="garden-game">
              <p className="garden-game-progress font-type">
                {picks.length + 1} / {STYLE_ITEMS.length}
              </p>
              <p className="garden-game-situation font-serif">{current.situation}</p>
              <p className="garden-hint font-serif ink-fade">此刻你心里的第一反应更接近哪一句？</p>
              <div className="garden-game-options">
                {current.options.map((o, i) => (
                  <button
                    key={i}
                    className="garden-game-option font-serif"
                    onClick={() => setPicks(prev => [...prev, o.optimistic])}
                  >
                    {o.text}
                  </button>
                ))}
              </div>
              {picks.length > 0 && (
                <button
                  className="garden-game-back font-type"
                  onClick={() => setPicks(prev => prev.slice(0, -1))}
                >
                  ‹ 上一题
                </button>
              )}
            </div>
          ) : (
            <div className="garden-perma">
              {STYLE_DIMENSIONS.map(d => {
                const r = result.byDimension[d];
                const pct = r.total ? Math.round((r.optimistic / r.total) * 100) : 0;
                return (
                  <div key={d} className="garden-perma-row">
                    <span className="garden-perma-label font-type">{STYLE_LABEL[d].zh}</span>
                    <span className="garden-perma-bar">
                      <span className="garden-perma-fill" style={{ width: `${pct}%` }} />
                    </span>
                    <span className="garden-perma-score font-type">{r.optimistic}/{r.total}</span>
                  </div>
                );
              })}
              <p className="garden-card-text font-serif" style={{ marginTop: "10px" }}>
                {styleVerdict(result.overall)}
              </p>
              {prevOptimism && (
                <p className="garden-hint font-serif ink-fade">
                  上次 {prevOptimism.overall} → 这次 {result.overall}
                  {result.overall > prevOptimism.overall
                    ? "，解释的方式松动了一点。"
                    : result.overall < prevOptimism.overall
                      ? "，今天也许只是累了。"
                      : "，和上次一样。"}
                </p>
              )}
              <p className="garden-hint font-serif ink-fade">
                条越满，说明你把挫折解释得越「暂时、局部、非全责」——这正是可以练习的乐观。
              </p>
              <button className="garden-btn font-type" onClick={() => setPicks(() => [])}>
                AGAIN · 再来一轮
              </button>
            </div>
          )}
        </section>

        {/* ----- character strengths ----- */}
        <section className="garden-block" id="strengths">
          <h2 className="garden-block-title font-type">SIGNATURE STRENGTHS · 品格优势</h2>

          {!strengthsDone && strengthCard ? (
            <div className="garden-game">
              <p className="garden-game-progress font-type">
                {strengthPicks.length + 1} / {STRENGTH_CARDS.length}
              </p>
              <p className="garden-hint font-serif ink-fade">哪一句更像你？</p>
              <div className="garden-game-options">
                <button
                  className="garden-game-option font-serif"
                  onClick={() => setStrengthPicks(prev => [...prev, strengthCard.a.strength])}
                >
                  {strengthCard.a.text}
                </button>
                <button
                  className="garden-game-option font-serif"
                  onClick={() => setStrengthPicks(prev => [...prev, strengthCard.b.strength])}
                >
                  {strengthCard.b.text}
                </button>
              </div>
              {strengthPicks.length > 0 && (
                <button
                  className="garden-game-back font-type"
                  onClick={() => setStrengthPicks(prev => prev.slice(0, -1))}
                >
                  ‹ 上一题
                </button>
              )}
            </div>
          ) : (
            <div className="garden-exchange">
              {top3.map((t, i) => (
                <div key={t.strength} className="garden-card">
                  <p className="garden-card-tag font-type">
                    NO. {i + 1} · {STRENGTH_LABEL[t.strength].zh}
                  </p>
                  <p className="garden-card-text font-serif">
                    {STRENGTH_LABEL[t.strength].desc}
                  </p>
                </div>
              ))}
              <p className="garden-hint font-serif ink-fade">
                这是你的签名优势——塞利格曼说，幸福不在修补短板，而在把它们用在每一天。
              </p>
              {prevStrengths && (
                <p className="garden-hint font-serif ink-fade">
                  上次的前三：{prevStrengths.top.map(t => STRENGTH_LABEL[t].zh).join("、")}
                  {prevStrengths.top.join() === top3.map(t => t.strength).join()
                    ? "——没有变，这就是「签名」的含义。"
                    : "——有些优势换了位置，人是会流动的。"}
                </p>
              )}
              <button className="garden-btn font-type" onClick={() => setStrengthPicks(() => [])}>
                AGAIN · 再测一次
              </button>
            </div>
          )}
        </section>

        {/* ----- bottle post ----- */}
        <section className="garden-block" id="bottle">
          <h2 className="garden-block-title font-type">BOTTLE POST · 瓶中信</h2>
          {bottleReceived === null ? (
            <div className="garden-share">
              <p className="garden-hint font-serif ink-fade" style={{ margin: "0 0 14px" }}>
                写一句话，给同样在深夜打开这个房间的人。投进雨里，会有一只别人的瓶子漂到你脚边。
              </p>
              <textarea
                className="garden-input font-serif"
                value={bottleText}
                onChange={e => setBottleText(e.target.value)}
                maxLength={200}
                rows={2}
                placeholder="写给陌生夜航者的一句话……"
              />
              <button
                className="garden-btn font-type"
                onClick={castBottle}
                disabled={!bottleText.trim() || bottleBusy}
              >
                {bottleBusy ? "CASTING…" : "CAST · 投进雨里"}
              </button>
            </div>
          ) : (
            <div className="garden-exchange">
              <div className="garden-card garden-card-match">
                <p className="garden-card-tag font-type">WASHED ASHORE · 漂到你脚边的瓶子</p>
                <p className="garden-card-text font-serif">“{bottleReceived}”</p>
              </div>
              <p className="garden-hint font-serif ink-fade">
                你的瓶子也已经在雨里了，会在某个深夜漂到另一个人脚边。
              </p>
              <button
                className="garden-game-back font-type"
                onClick={() => setBottleReceived(null)}
              >
                再投一只
              </button>
            </div>
          )}
        </section>

        {/* ----- time capsule ----- */}
        <section className="garden-block" id="capsule">
          <h2 className="garden-block-title font-type">TIME CAPSULE · 时间胶囊</h2>
          <p className="garden-hint font-serif ink-fade" style={{ margin: "0 0 14px" }}>
            给未来的自己写一封信。封好之后，不到日子谁也打不开——包括你。
          </p>
          <div className="garden-share">
            <textarea
              className="garden-input font-serif"
              value={capsuleText}
              onChange={e => setCapsuleText(e.target.value)}
              maxLength={600}
              rows={3}
              placeholder="亲爱的未来的我，现在……"
            />
            <div className="garden-capsule-days">
              {[{ d: 90, zh: "三个月后" }, { d: 180, zh: "半年后" }, { d: 365, zh: "一年后" }].map(o => (
                <button
                  key={o.d}
                  className={`garden-nav-item font-type ${capsuleDays === o.d ? "garden-nav-item-on" : ""}`}
                  onClick={() => setCapsuleDays(o.d)}
                >
                  {o.zh}
                </button>
              ))}
            </div>
            <button
              className="garden-btn font-type"
              onClick={sealCapsule}
              disabled={!capsuleText.trim() || capsuleBusy}
            >
              {capsuleBusy ? "SEALING…" : "SEAL · 落蜡封存"}
            </button>
          </div>
          {capsules.length > 0 && (
            <ul className="garden-capsule-list">
              {capsules.map(c => (
                <li key={c.id} className="garden-card">
                  {c.sealed ? (
                    <>
                      <p className="garden-card-tag font-type">SEALED · 开启于 {todayKey(new Date(c.openAt))}</p>
                      <p className="garden-capsule-wax" aria-hidden />
                    </>
                  ) : (
                    <>
                      <p className="garden-card-tag font-type">
                        OPENED · 写于 {todayKey(new Date(c.createdAt))}
                      </p>
                      <p className="garden-card-text font-serif">{c.text}</p>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* ----- suitcase ----- */}
        <section className="garden-block" id="suitcase">
          <h2 className="garden-block-title font-type">SUITCASE · 记录的携带</h2>
          <p className="garden-hint font-serif ink-fade" style={{ margin: "0 0 14px" }}>
            这个房间的记录只住在当前浏览器里。换设备前把它们打包带走，到新房间再放下。
          </p>
          <div className="garden-suitcase-actions">
            <button className="garden-btn font-type" onClick={exportSuitcase}>
              EXPORT · 打包带走
            </button>
            <label className="garden-btn font-type garden-suitcase-import">
              IMPORT · 放下行李
              <input
                type="file"
                accept="application/json"
                onChange={e => importSuitcase(e.target.files?.[0])}
              />
            </label>
          </div>
          {portNote && <p className="garden-hint font-serif ink-fade">{portNote}</p>}
        </section>

        {/* ----- five questions ----- */}
        <section className="garden-block" id="questions">
          <h2 className="garden-block-title font-type">FIVE QUESTIONS · 认识自己的五个问题</h2>
          <ul className="garden-q-list">
            {FIVE_QUESTIONS.map((q, i) => (
              <li key={q.pillar} className="garden-q">
                <p className="garden-q-head font-serif">
                  <span className="garden-q-letter font-type">{PILLAR_LABEL[q.pillar].letter}</span>
                  {q.zh}
                  <span className="garden-q-en ink-mute"> {q.en}</span>
                </p>
                <input
                  className="garden-input font-serif"
                  value={answers[q.pillar]}
                  onChange={e => setAnswer(q.pillar, e.target.value)}
                  placeholder={`第 ${i + 1} 问，一句话即可`}
                />
              </li>
            ))}
          </ul>

          <button
            className="garden-btn font-type"
            onClick={() => setRevealed(true)}
            disabled={!answeredAll}
          >
            REVEAL · 看看我的五个支柱
          </button>

          {revealed && answeredAll && (
            <div className="garden-perma">
              {PILLARS.map(p => (
                <div key={p} className="garden-perma-row">
                  <span className="garden-perma-label font-type">
                    {PILLAR_LABEL[p].letter} · {PILLAR_LABEL[p].zh}
                  </span>
                  <span className="garden-perma-bar">
                    <span
                      className="garden-perma-fill"
                      style={{ width: `${scores[p]}%` }}
                    />
                  </span>
                  <span className="garden-perma-score font-type">{scores[p]}</span>
                </div>
              ))}
              <p className="garden-hint font-serif italic ink-fade">
                这不是测验，只是一面镜子——哪一栏最短，哪里就值得多浇一点水。
              </p>
            </div>
          )}
        </section>
      </section>

      <aside className="archive-window">
        <WindowDateChip />
        <p className="window-quote font-serif italic">
          “Well-being is not the absence of storms, but a garden kept through them.”
          <span className="window-quote-zh ink-fade font-serif">幸福不是无风无雨，而是一座被照料过的花园。</span>
        </p>
      </aside>

      {greeting && (
        <div className="garden-greet" onClick={dismissGreeting} role="dialog" aria-label="welcome">
          <div className="garden-greet-card">
            <p className="font-serif">这里是花园。</p>
            <p className="font-serif ink-fade">
              每天种下一条很小的好消息，它会换回另一位访客的一条；
              睡前记下三件好事，油灯会越烧越亮。
            </p>
            <p className="font-serif ink-mute">（点击任意处进入）</p>
          </div>
        </div>
      )}
    </main>
  );
}
