// Flow sessions — Csikszentmihalyi's experience sampling, scaled down to a
// focus timer and a two-axis check-in, kept per-browser.

export interface FlowSession {
  id: string;
  intention: string;
  plannedMin: number;
  actualMin: number;
  challenge: number; // 1-9
  skill: number; // 1-9
  state: FlowState;
  createdAt: number;
}

export type FlowState =
  | "flow"
  | "arousal"
  | "anxiety"
  | "control"
  | "relaxation"
  | "boredom"
  | "apathy"
  | "worry";

export const STATE_LABEL: Record<FlowState, { zh: string; note: string }> = {
  flow:       { zh: "心流",   note: "挑战与能力都很高，且彼此相当——这就是时间消失的地方。" },
  arousal:    { zh: "唤醒",   note: "挑战略高于能力。再练一点，就是心流。" },
  anxiety:    { zh: "焦虑",   note: "挑战远高于能力。把任务拆小，或者先补一块技能。" },
  control:    { zh: "掌控",   note: "能力略高于挑战。舒服，但可以试着抬高一点目标。" },
  relaxation: { zh: "放松",   note: "能力绰绰有余。适合恢复，不适合成长。" },
  boredom:    { zh: "无聊",   note: "能力远高于挑战。给自己加一个限制或新花样。" },
  apathy:     { zh: "淡漠",   note: "挑战与能力都低。这件事也许根本不值得做，换一件。" },
  worry:      { zh: "担忧",   note: "挑战一般但自觉能力不足。多半是没睡好——先照顾自己。" },
};

// Csikszentmihalyi's eight-channel model over the challenge/skill plane.
export function flowState(challenge: number, skill: number): FlowState {
  const hi = (v: number) => v >= 6;
  const lo = (v: number) => v <= 4;
  if (hi(challenge) && hi(skill)) return challenge > skill + 2 ? "arousal" : skill > challenge + 2 ? "control" : "flow";
  if (hi(challenge) && lo(skill)) return "anxiety";
  if (lo(challenge) && hi(skill)) return skill > 7 ? "relaxation" : "boredom";
  if (lo(challenge) && lo(skill)) return "apathy";
  if (challenge > skill) return "worry";
  if (skill > challenge) return "control";
  return "flow";
}

const KEY = "room1913.flow.v1";

export function loadFlowLog(): FlowSession[] {
  try {
    const list = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function appendFlowSession(s: FlowSession): FlowSession[] {
  const list = [...loadFlowLog(), s];
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch {}
  return list;
}
