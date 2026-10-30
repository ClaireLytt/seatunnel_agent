"use client";
import { useEffect, useState } from "react";
import SessionRail from "../components/SessionRail";
import WindowDateChip from "../components/WindowDateChip";
import { CHARACTERS } from "../characters";
import { SCENES, SCENES_CLASSIC, DialogueScene } from "../lib/dialogues";

const ANSWERS_KEY = "room1913.salon.v1";

function loadAnswers(): Record<string, string> {
  try {
    const v = JSON.parse(localStorage.getItem(ANSWERS_KEY) ?? "{}");
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}

function Scene({
  scene,
  answer,
  onAnswer,
}: {
  scene: DialogueScene;
  answer: string | undefined;
  onAnswer: (v: string) => void;
}) {
  const [revealed, setRevealed] = useState(answer !== undefined ? scene.turns.length : 0);
  const [draft, setDraft] = useState(answer ?? "");
  const open = revealed > 0;
  const finished = revealed >= scene.turns.length;

  return (
    <li className="salon-scene">
      <button
        className="salon-scene-head"
        onClick={() => setRevealed(r => (r === 0 ? 1 : r))}
        aria-expanded={open}
      >
        <span className="salon-scene-title font-serif">{scene.title}</span>
        <span className="salon-scene-en font-type">{scene.titleEn}</span>
      </button>

      {open && (
        <div className="salon-scene-body">
          {scene.turns.slice(0, revealed).map((t, i) => {
            const c = CHARACTERS[t.who];
            return (
              <p key={i} className="salon-turn font-serif">
                <span className="salon-turn-who font-type" style={{ color: c.color }}>
                  {c.zhName}
                </span>
                {t.text}
              </p>
            );
          })}

          {!finished ? (
            <button
              className="garden-game-back font-type"
              onClick={() => setRevealed(r => r + 1)}
            >
              继续听 ›
            </button>
          ) : scene.ask ? (
            answer !== undefined ? (
              <div className="salon-ask">
                <p className="garden-hint font-serif ink-fade">{scene.ask}</p>
                <p className="salon-answer font-serif">你当时写下：{answer}</p>
              </div>
            ) : (
              <div className="salon-ask">
                <p className="garden-hint font-serif ink-fade">
                  两人同时看向你。{scene.ask}
                </p>
                <input
                  className="garden-input font-serif"
                  value={draft}
                  onChange={e => setDraft(e.target.value)}
                  maxLength={120}
                  placeholder="一句话即可，只有你自己看得到"
                />
                <button
                  className="garden-btn font-type"
                  onClick={() => draft.trim() && onAnswer(draft.trim())}
                  disabled={!draft.trim()}
                >
                  ANSWER · 轻声回答
                </button>
              </div>
            )
          ) : null}
        </div>
      )}
    </li>
  );
}

export default function Salon() {
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => { setAnswers(loadAnswers()); }, []);

  const saveAnswer = (sceneId: string, v: string) => {
    setAnswers(prev => {
      const next = { ...prev, [sceneId]: v };
      try { localStorage.setItem(ANSWERS_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  };

  return (
    <main className="archive-shell">
      <SessionRail active="salon" />

      <section className="archive-stage">
        <header className="archive-stage-head">
          <h1 className="archive-stage-title font-serif">SALON</h1>
          <p className="archive-stage-sub font-serif ink-fade">
            两位现代访客的夜谈，偶尔有一句问向你
          </p>
        </header>

        <h2 className="salon-volume font-type">VOL. I · 两位现代访客</h2>
        <ul className="salon-list">
          {SCENES.map(s => (
            <Scene
              key={s.id}
              scene={s}
              answer={answers[s.id]}
              onAnswer={v => saveAnswer(s.id, v)}
            />
          ))}
        </ul>

        <h2 className="salon-volume font-type">VOL. II · 1913 年的四人</h2>
        <ul className="salon-list">
          {SCENES_CLASSIC.map(s => (
            <Scene
              key={s.id}
              scene={s}
              answer={answers[s.id]}
              onAnswer={v => saveAnswer(s.id, v)}
            />
          ))}
        </ul>
      </section>

      <aside className="archive-window">
        <WindowDateChip />
        <p className="window-quote font-serif italic">
          “Two lamps, one table, and the rain for a third voice.”
          <span className="window-quote-zh ink-fade font-serif">两盏灯，一张桌，雨声算第三个声音。</span>
        </p>
      </aside>
    </main>
  );
}
