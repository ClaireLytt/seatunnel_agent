// Dream log — the garden's dark twin. A dream written down at dawn is
// keyword-read into the room's seven subconscious dimensions and lets the
// map breathe with a second source besides sealed sessions.

import { DIMENSIONS, type Dimension } from "./dimensions";

// reuse the spirit of lib/dimensions.ts keywords, tuned for dream language
const DREAM_KEYWORDS: Record<Dimension, string[]> = {
  desire: ["想要", "追", "抓不住", "渴", "吻", "身体", "赤", "饿", "偷", "欲"],
  order: ["迟到", "考试", "排队", "规则", "警察", "清单", "锁", "整理", "秩序", "任务"],
  shadow: ["追赶", "怪物", "黑", "坠落", "牙齿", "死", "血", "怕", "藏", "影子", "蛇"],
  rationality: ["数字", "地图", "计算", "书", "答案", "机器", "证明", "逻辑", "钟"],
  sensitivity: ["哭", "拥抱", "告别", "旧", "童年", "外婆", "信", "温", "疼", "想念"],
  isolation: ["一个人", "空", "找不到", "迷路", "无人", "荒", "墙", "门关", "听不见", "远"],
  dream: ["飞", "水", "海", "楼梯", "镜子", "变成", "重复", "醒不来", "漂", "雾", "月"],
};

export interface DreamEntry {
  id: string;
  text: string;
  day: string;
  dims: Dimension[]; // top dimensions read from the text
  createdAt: number;
}

export function readDream(text: string): Dimension[] {
  const t = text.toLowerCase();
  const scored = DIMENSIONS.map(d => {
    let hits = 0;
    for (const w of DREAM_KEYWORDS[d]) if (t.includes(w)) hits++;
    return { d, hits };
  })
    .filter(s => s.hits > 0)
    .sort((a, b) => b.hits - a.hits);
  // every dream carries the dream dimension at least
  const dims = scored.slice(0, 2).map(s => s.d);
  return dims.length ? dims : ["dream"];
}

const KEY = "room1913.dreams.v1";

export function loadDreams(): DreamEntry[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

export function appendDream(text: string): DreamEntry[] {
  const now = new Date();
  const entry: DreamEntry = {
    id: `dr-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    text: text.trim(),
    day: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`,
    dims: readDream(text),
    createdAt: Date.now(),
  };
  const list = [...loadDreams(), entry];
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch {}
  return list;
}

// How much recent dreams lean on each dimension: a small nudge (0-8 per
// dimension) blended into the radar, decaying over the last ten dreams.
export function dreamBias(dreams: DreamEntry[]): Partial<Record<Dimension, number>> {
  const recent = dreams.slice(-10);
  const bias: Partial<Record<Dimension, number>> = {};
  for (const dr of recent) {
    for (const d of dr.dims) bias[d] = (bias[d] ?? 0) + 2;
  }
  for (const d of Object.keys(bias) as Dimension[]) {
    bias[d] = Math.min(8, bias[d]!);
  }
  return bias;
}
