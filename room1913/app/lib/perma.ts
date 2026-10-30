// PERMA — Seligman's five pillars of well-being.
// Deterministic: keyword scoring in the style of lib/dimensions.ts, no LLM needed.

export const PILLARS = [
  "positive",
  "engagement",
  "relationships",
  "meaning",
  "accomplishment",
] as const;
export type Pillar = (typeof PILLARS)[number];

export const PILLAR_LABEL: Record<Pillar, { en: string; zh: string; letter: string }> = {
  positive:       { en: "Positive Emotion", zh: "积极情绪", letter: "P" },
  engagement:     { en: "Engagement",       zh: "投入",     letter: "E" },
  relationships:  { en: "Relationships",    zh: "人际关系", letter: "R" },
  meaning:        { en: "Meaning",          zh: "意义",     letter: "M" },
  accomplishment: { en: "Accomplishment",   zh: "成就",     letter: "A" },
};

// 认识自己的五个问题 — one question per pillar.
export const FIVE_QUESTIONS: { pillar: Pillar; en: string; zh: string }[] = [
  {
    pillar: "positive",
    en: "When did you last laugh without reason?",
    zh: "你上一次毫无理由地笑，是什么时候？",
  },
  {
    pillar: "engagement",
    en: "Doing what do you forget the clock?",
    zh: "做什么事时，你会忘记时间？",
  },
  {
    pillar: "relationships",
    en: "Who would you call at three in the morning?",
    zh: "凌晨三点，你会打电话给谁？",
  },
  {
    pillar: "meaning",
    en: "What would you keep doing if no one ever knew?",
    zh: "如果永远无人知晓，你仍会坚持做什么？",
  },
  {
    pillar: "accomplishment",
    en: "What small thing did you finish that no one applauded?",
    zh: "你完成过什么没人鼓掌、但你自己记得的小事？",
  },
];

const KEYWORDS: Record<Pillar, string[]> = {
  positive: ["开心","快乐","高兴","笑","喜悦","温暖","阳光","happy","joy","laugh","smile","好吃","美","舒服","晴","treat","delicious","开怀"],
  engagement: ["专注","投入","沉浸","心流","练习","学会","flow","focus","absorbed","hobby","画","弹","跑步","读完","写完","做饭","手工","拼"],
  relationships: ["朋友","家人","妈妈","爸爸","同事","聊天","拥抱","一起","friend","family","together","hug","call","陪","请客","久别","重逢","猫","狗"],
  meaning: ["意义","帮助","志愿","感恩","感谢","世界","相信","meaning","help","grateful","thanks","volunteer","捐","善意","被需要","传承"],
  accomplishment: ["完成","达成","通过","考过","晋升","搞定","修好","坚持","finish","done","pass","achieve","promotion","fix","第一次","终于","目标"],
};

export function classifyPillar(text: string): Pillar {
  const t = text.toLowerCase();
  let best: Pillar = "positive";
  let bestHits = -1;
  for (const p of PILLARS) {
    let hits = 0;
    for (const w of KEYWORDS[p]) {
      if (t.includes(w.toLowerCase())) hits++;
    }
    if (hits > bestHits) { bestHits = hits; best = p; }
  }
  return best;
}

// Score one free-text answer for its own pillar: presence + richness, 0–100.
export function scoreAnswer(pillar: Pillar, answer: string): number {
  const t = answer.trim().toLowerCase();
  if (!t) return 0;
  let hits = 0;
  for (const w of KEYWORDS[pillar]) {
    if (t.includes(w.toLowerCase())) hits++;
  }
  const fromLength = Math.min(40, Math.round(t.length / 3)); // writing more = engaging more
  const fromHits = Math.min(40, hits * 12);
  return Math.max(10, Math.min(100, 20 + fromLength + fromHits));
}

export interface GoodNews {
  id: string;
  clientId: string;
  text: string;
  pillar: Pillar;
  day: string; // YYYY-MM-DD
  createdAt: number;
  litBy?: string[]; // visitors who lit a lamp back for this note
  replies?: { clientId: string; text: string; at: number }[]; // one line back, one per visitor
}

export function todayKey(now = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
