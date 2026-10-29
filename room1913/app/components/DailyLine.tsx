"use client";
import { useEffect, useState } from "react";
import { CHARACTERS } from "../characters";
import { dailyLine } from "../lib/dialogues";

// One line from the salon, left on the door each day. Computed on the
// client so the date is the visitor's, not the build's.
export default function DailyLine() {
  const [line, setLine] = useState<{ text: string; zh: string } | null>(null);

  useEffect(() => {
    const l = dailyLine();
    setLine({ text: l.text, zh: CHARACTERS[l.who].zhName ?? CHARACTERS[l.who].name });
  }, []);

  if (!line) return null;
  return (
    <p className="daily-line font-serif">
      “{line.text}”
      <span className="daily-line-who font-type">—— {line.zh} · 今日一句</span>
    </p>
  );
}
