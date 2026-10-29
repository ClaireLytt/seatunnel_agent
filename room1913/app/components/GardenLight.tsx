"use client";
import { useEffect, useState } from "react";
import {
  PILLARS,
  PILLAR_LABEL,
  Pillar,
  GoodNews,
  scoreAnswer,
} from "../lib/perma";

// The garden's answer to the subconscious map: a small warm radar of the
// five PERMA pillars, fed by the five questions and shared good news.

const ANSWERS_KEY = "room1913.garden.answers.v1";
const CLIENT_KEY = "room1913.garden.client.v1";

function pillarScores(
  answers: Partial<Record<Pillar, string>>,
  history: GoodNews[]
): Record<Pillar, number> {
  const counts = new Map<Pillar, number>();
  for (const n of history) counts.set(n.pillar, (counts.get(n.pillar) ?? 0) + 1);
  return Object.fromEntries(
    PILLARS.map(p => {
      const base = scoreAnswer(p, answers[p] ?? "");
      const bonus = Math.min(30, (counts.get(p) ?? 0) * 10);
      return [p, Math.min(100, base + bonus)];
    })
  ) as Record<Pillar, number>;
}

export default function GardenLight() {
  const [values, setValues] = useState<Record<Pillar, number> | null>(null);
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    let answers: Partial<Record<Pillar, string>> = {};
    let clientId = "";
    try {
      answers = JSON.parse(localStorage.getItem(ANSWERS_KEY) ?? "{}");
      clientId = localStorage.getItem(CLIENT_KEY) ?? "";
    } catch {}
    const answered = Object.values(answers).some(v => (v ?? "").trim());
    fetch(`/api/goodnews?clientId=${encodeURIComponent(clientId)}`)
      .then(r => r.json())
      .then(d => {
        const history: GoodNews[] = Array.isArray(d.history) ? d.history : [];
        setHasData(answered || history.length > 0);
        setValues(pillarScores(answers, history));
      })
      .catch(() => {
        setHasData(answered);
        setValues(pillarScores(answers, []));
      });
  }, []);

  if (!values) return null;

  const size = 240;
  const cx = size / 2;
  const cy = size / 2;
  const R = 82;
  const N = PILLARS.length;
  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / N;
  const point = (i: number, r: number) =>
    [cx + Math.cos(angle(i)) * r, cy + Math.sin(angle(i)) * r] as const;

  const rings = [0.33, 0.66, 1].map(k =>
    PILLARS.map((_, i) => point(i, R * k).join(",")).join(" ")
  );
  const dataPoly = PILLARS.map((p, i) =>
    point(i, R * (values[p] / 100)).join(",")
  ).join(" ");

  return (
    <div className="garden-light">
      <p className="garden-light-title font-type">GARDEN LIGHT · 花园之光</p>
      {hasData ? (
        <>
          <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label="PERMA radar">
            {rings.map((pts, i) => (
              <polygon key={i} className="garden-light-ring" points={pts} />
            ))}
            {PILLARS.map((p, i) => {
              const [x, y] = point(i, R);
              return <line key={p} className="garden-light-axis" x1={cx} y1={cy} x2={x} y2={y} />;
            })}
            <polygon className="garden-light-data" points={dataPoly} />
            {PILLARS.map((p, i) => {
              const [lx, ly] = point(i, R + 18);
              return (
                <text
                  key={p}
                  className="garden-light-label"
                  x={lx}
                  y={ly}
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {PILLAR_LABEL[p].letter}
                </text>
              );
            })}
          </svg>
          <ul className="garden-light-legend">
            {PILLARS.map(p => (
              <li key={p} className="font-type">
                {PILLAR_LABEL[p].letter} · {PILLAR_LABEL[p].zh}
                <span className="garden-light-num">{Math.round(values[p])}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="map-empty font-serif ink-mute" style={{ padding: "18px 0" }}>
          去花园回答五个问题、分享一条好消息，这里会亮起来。
        </p>
      )}
    </div>
  );
}
