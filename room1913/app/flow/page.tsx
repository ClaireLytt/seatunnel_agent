"use client";
import { useEffect, useRef, useState } from "react";
import SessionRail from "../components/SessionRail";
import WindowDateChip from "../components/WindowDateChip";
import {
  FlowSession,
  STATE_LABEL,
  appendFlowSession,
  flowState,
  loadFlowLog,
} from "../lib/flow";

const DURATIONS = [15, 25, 50];

type Stage = "setup" | "running" | "checkin" | "done";

const STATE_COLOR: Record<string, string> = {
  flow: "#d99a4e",
  arousal: "#c9b36a",
  control: "#8fb3a8",
  anxiety: "#b87a4a",
  worry: "#b87a4a",
  relaxation: "#9fb88a",
  boredom: "#8a8a7a",
  apathy: "#6a665e",
};

// Sessions plotted on Csikszentmihalyi's challenge-by-skill plane.
function FlowMap({ log }: { log: FlowSession[] }) {
  if (log.length < 2) return null;
  const size = 300;
  const pad = 34;
  const scale = (v: number) => pad + ((v - 1) / 8) * (size - 2 * pad);
  const x = (skill: number) => scale(skill);
  const y = (challenge: number) => size - scale(challenge);
  return (
    <section className="garden-block">
      <h2 className="garden-block-title font-type">FLOW MAP · 你的心流地图</h2>
      <svg className="flow-map" viewBox={`0 0 ${size} ${size}`} role="img" aria-label="flow map">
        {/* the flow channel: a soft diagonal band */}
        <polygon
          points={`${x(2.5)},${y(1)} ${x(9)},${y(7.5)} ${x(9)},${y(9)} ${x(7.5)},${y(9)} ${x(1)},${y(2.5)} ${x(1)},${y(1)}`}
          fill="rgba(217,154,78,0.07)"
        />
        <rect x={pad} y={size - scale(9)} width={size - 2 * pad} height={size - 2 * pad}
          fill="none" stroke="rgba(217,154,78,0.18)" />
        <line x1={x(1)} y1={y(1)} x2={x(9)} y2={y(9)} stroke="rgba(217,154,78,0.25)" strokeDasharray="3 4" />
        <text className="flow-map-label" x={x(2)} y={y(8.3)}>焦虑</text>
        <text className="flow-map-label" x={x(7.6)} y={y(8.6)}>心流</text>
        <text className="flow-map-label" x={x(7.8)} y={y(1.6)}>无聊</text>
        <text className="flow-map-label" x={x(1.9)} y={y(1.4)}>淡漠</text>
        <text className="flow-map-axis" x={size / 2} y={size - 6} textAnchor="middle">能力 →</text>
        <text className="flow-map-axis" x={10} y={size / 2} textAnchor="middle"
          transform={`rotate(-90 10 ${size / 2})`}>挑战 →</text>
        {log.map(s => (
          <circle
            key={s.id}
            cx={x(s.skill)}
            cy={y(s.challenge)}
            r={Math.min(9, 3.5 + s.actualMin / 15)}
            fill={STATE_COLOR[s.state] ?? "#8a8a7a"}
            fillOpacity="0.75"
            stroke="rgba(232,220,196,0.35)"
            strokeWidth="0.6"
          >
            <title>{`${s.intention} · ${STATE_LABEL[s.state].zh} · ${s.actualMin} 分钟`}</title>
          </circle>
        ))}
      </svg>
      <p className="garden-hint font-serif ink-fade">
        每个点是一段专注；点越大做得越久。愿它们慢慢聚向对角线的上端。
      </p>
    </section>
  );
}

export default function Flow() {
  const [stage, setStage] = useState<Stage>("setup");
  const [intention, setIntention] = useState("");
  const [plannedMin, setPlannedMin] = useState(25);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [challenge, setChallenge] = useState(5);
  const [skill, setSkill] = useState(5);
  const [log, setLog] = useState<FlowSession[]>([]);
  const startedAt = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setLog(loadFlowLog());
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  const start = () => {
    if (!intention.trim()) return;
    startedAt.current = Date.now();
    setSecondsLeft(plannedMin * 60);
    setStage("running");
    window.dispatchEvent(new CustomEvent("room1913:hush", { detail: { mul: 0.4, ms: 900 } }));
    timer.current = setInterval(() => {
      setSecondsLeft(s => {
        if (s <= 1) {
          if (timer.current) clearInterval(timer.current);
          setStage("checkin");
          window.dispatchEvent(new CustomEvent("room1913:hush", { detail: { mul: 1, ms: 1400 } }));
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  };

  const finishEarly = () => {
    if (timer.current) clearInterval(timer.current);
    setStage("checkin");
    window.dispatchEvent(new CustomEvent("room1913:hush", { detail: { mul: 1, ms: 1400 } }));
  };

  const save = () => {
    const actualMin = Math.max(1, Math.round((Date.now() - startedAt.current) / 60000));
    const state = flowState(challenge, skill);
    const session: FlowSession = {
      id: `fl-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      intention: intention.trim(),
      plannedMin,
      actualMin,
      challenge,
      skill,
      state,
      createdAt: Date.now(),
    };
    setLog(appendFlowSession(session));
    setStage("done");
  };

  const reset = () => {
    setIntention("");
    setChallenge(5);
    setSkill(5);
    setStage("setup");
  };

  const mmss = `${String(Math.floor(secondsLeft / 60)).padStart(2, "0")}:${String(secondsLeft % 60).padStart(2, "0")}`;
  const lastState = log.length ? log[log.length - 1].state : null;

  return (
    <main className="archive-shell">
      <SessionRail active="flow" />

      <section className="archive-stage">
        <header className="archive-stage-head">
          <h1 className="archive-stage-title font-serif">FLOW</h1>
          <p className="archive-stage-sub font-serif ink-fade">
            挑战与能力相遇的地方，时钟停摆
          </p>
        </header>

        {stage === "setup" && (
          <section className="garden-block">
            <h2 className="garden-block-title font-type">ONE THING · 只做一件事</h2>
            <div className="garden-share">
              <input
                className="garden-input font-serif"
                value={intention}
                onChange={e => setIntention(e.target.value)}
                maxLength={80}
                placeholder="接下来这段时间，你只做哪一件事？"
              />
              <div className="garden-capsule-days">
                {DURATIONS.map(d => (
                  <button
                    key={d}
                    className={`garden-nav-item font-type ${plannedMin === d ? "garden-nav-item-on" : ""}`}
                    onClick={() => setPlannedMin(d)}
                  >
                    {d} 分钟
                  </button>
                ))}
              </div>
              <button
                className="garden-btn font-type"
                onClick={start}
                disabled={!intention.trim()}
              >
                BEGIN · 把表交给雨声
              </button>
            </div>
          </section>
        )}

        {stage === "running" && (
          <section className="garden-block flow-running">
            <p className="flow-intention font-serif ink-fade">{intention}</p>
            <p className="flow-clock font-type">{mmss}</p>
            <button className="garden-game-back font-type" onClick={finishEarly}>
              提前结束
            </button>
          </section>
        )}

        {stage === "checkin" && (
          <section className="garden-block">
            <h2 className="garden-block-title font-type">CHECK-IN · 刚才那段时间</h2>
            <div className="flow-sliders">
              <label className="flow-slider-row">
                <span className="garden-perma-label font-type">这件事的挑战</span>
                <input
                  type="range" min={1} max={9} value={challenge}
                  onChange={e => setChallenge(Number(e.target.value))}
                />
                <span className="garden-perma-score font-type">{challenge}</span>
              </label>
              <label className="flow-slider-row">
                <span className="garden-perma-label font-type">你的能力感</span>
                <input
                  type="range" min={1} max={9} value={skill}
                  onChange={e => setSkill(Number(e.target.value))}
                />
                <span className="garden-perma-score font-type">{skill}</span>
              </label>
            </div>
            <button className="garden-btn font-type" onClick={save}>
              MARK · 记在表上
            </button>
          </section>
        )}

        {stage === "done" && lastState && (
          <section className="garden-block">
            <h2 className="garden-block-title font-type">
              {STATE_LABEL[lastState].zh}
            </h2>
            <p className="garden-card-text font-serif">{STATE_LABEL[lastState].note}</p>
            <button className="garden-btn font-type" onClick={reset}>
              AGAIN · 再来一段
            </button>
          </section>
        )}

        {stage !== "running" && <FlowMap log={log} />}

        {log.length > 0 && stage !== "running" && (
          <section className="garden-block">
            <h2 className="garden-block-title font-type">LOGBOOK · 心流日志</h2>
            <ul className="garden-capsule-list">
              {[...log].reverse().slice(0, 8).map(s => (
                <li key={s.id} className="garden-card">
                  <p className="garden-card-tag font-type">
                    {STATE_LABEL[s.state].zh} · {s.actualMin} 分钟 · 挑战 {s.challenge} / 能力 {s.skill}
                  </p>
                  <p className="garden-card-text font-serif">{s.intention}</p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </section>

      <aside className="archive-window">
        <WindowDateChip />
        <p className="window-quote font-serif italic">
          “The best moments occur when a person's body or mind is stretched to its limits.”
          <span className="window-quote-zh ink-fade font-serif">最好的时刻，发生在身心被恰好用尽之处。</span>
        </p>
      </aside>
    </main>
  );
}
