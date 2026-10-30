"use client";
import { useEffect, useState } from "react";
import { DIM_LABEL_ZH } from "../lib/dimensions";
import { DreamEntry, appendDream, loadDreams } from "../lib/dreams";

// The dawn-side of the good-news garden: write a dream down, the room
// reads which dimensions it leans on, and the subconscious map listens.

export default function DreamLog({ onChange }: { onChange: (dreams: DreamEntry[]) => void }) {
  const [dreams, setDreams] = useState<DreamEntry[]>([]);
  const [draft, setDraft] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const list = loadDreams();
    setDreams(list);
    onChange(list);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const keep = () => {
    const text = draft.trim();
    if (!text) return;
    const list = appendDream(text);
    setDreams(list);
    onChange(list);
    setDraft("");
  };

  const recent = [...dreams].reverse().slice(0, 5);

  return (
    <div className="garden-block dream-log">
      <h2 className="garden-block-title font-type">DREAM LOG · 梦之档案</h2>
      <p className="garden-hint font-serif ink-fade" style={{ margin: "0 0 14px" }}>
        醒来时还记得什么，就写下什么。房间会读出它靠向哪个维度，地图听得见。
      </p>
      <div className="garden-share">
        <textarea
          className="garden-input font-serif"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          maxLength={400}
          rows={3}
          placeholder="昨夜，我梦见……"
        />
        <button className="garden-btn font-type" onClick={keep} disabled={!draft.trim()}>
          KEEP · 存入档案
        </button>
      </div>

      {dreams.length > 0 && (
        <div className="garden-past">
          <button className="garden-game-back font-type" onClick={() => setOpen(v => !v)}>
            {open ? "‹ 收起梦的记录" : `梦的记录 · ${dreams.length} 则 ›`}
          </button>
          {open && (
            <ul className="garden-past-list">
              {recent.map(d => (
                <li key={d.id} className="garden-card">
                  <p className="garden-card-tag font-type">
                    {d.day} · {d.dims.map(x => DIM_LABEL_ZH[x]).join(" · ")}
                  </p>
                  <p className="garden-card-text font-serif">{d.text}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
