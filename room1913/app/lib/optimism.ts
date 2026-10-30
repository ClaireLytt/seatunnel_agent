// Learned Optimism — Seligman's ABC explanatory-style exercise as a small
// deterministic card game. Three dimensions, three cards each.

export const STYLE_DIMENSIONS = ["permanence", "pervasiveness", "personalization"] as const;
export type StyleDimension = (typeof STYLE_DIMENSIONS)[number];

export const STYLE_LABEL: Record<StyleDimension, { zh: string; optimist: string; pessimist: string }> = {
  permanence:      { zh: "永久性",   optimist: "这只是暂时的", pessimist: "这会一直如此" },
  pervasiveness:   { zh: "普遍性",   optimist: "只是这一件事", pessimist: "我的生活全完了" },
  personalization: { zh: "个人化",   optimist: "也有环境的原因", pessimist: "全是我的错" },
};

export interface StyleItem {
  situation: string;
  dimension: StyleDimension;
  // exactly two readings of the same setback; `optimistic` marks the resilient one
  options: { text: string; optimistic: boolean }[];
}

export const STYLE_ITEMS: StyleItem[] = [
  {
    situation: "面试结束后，对方说「我们会再联系你」，然后杳无音信。",
    dimension: "permanence",
    options: [
      { text: "我大概永远过不了面试这一关。", optimistic: false },
      { text: "这一场没对上，下一场重新来。", optimistic: true },
    ],
  },
  {
    situation: "你精心准备的晚餐烧糊了。",
    dimension: "permanence",
    options: [
      { text: "今天手气不好，下次换个火候。", optimistic: true },
      { text: "我做饭从来就没成功过。", optimistic: false },
    ],
  },
  {
    situation: "坚持了两周的晨跑，这周一天都没去。",
    dimension: "permanence",
    options: [
      { text: "我总是半途而废，这次也一样。", optimistic: false },
      { text: "这周太累了，下周一再捡起来。", optimistic: true },
    ],
  },
  {
    situation: "你在会议上说错了一个数据，被当场指出。",
    dimension: "pervasiveness",
    options: [
      { text: "一个数字记岔了，更正就是。", optimistic: true },
      { text: "我整个人都不适合这份工作。", optimistic: false },
    ],
  },
  {
    situation: "朋友聚会上，你讲的笑话没人笑。",
    dimension: "pervasiveness",
    options: [
      { text: "我是个无趣的人，社交一塌糊涂。", optimistic: false },
      { text: "这个梗没接住而已，话题继续。", optimistic: true },
    ],
  },
  {
    situation: "你养的绿萝黄了一半叶子。",
    dimension: "pervasiveness",
    options: [
      { text: "浇水的节奏不对，调一调。", optimistic: true },
      { text: "我什么都养不活，什么都照顾不好。", optimistic: false },
    ],
  },
  {
    situation: "深夜给朋友发的消息，第二天中午还没回。",
    dimension: "personalization",
    options: [
      { text: "肯定是我说错了什么话让人烦了。", optimistic: false },
      { text: "人们都很忙，未必和我有关。", optimistic: true },
    ],
  },
  {
    situation: "小组项目没有按期完成。",
    dimension: "personalization",
    options: [
      { text: "进度受很多环节影响，不全在我。", optimistic: true },
      { text: "都怪我拖累了所有人。", optimistic: false },
    ],
  },
  {
    situation: "考试成绩比预期低了不少。",
    dimension: "personalization",
    options: [
      { text: "这次题目偏，准备方向也可以再调。", optimistic: true },
      { text: "是我太笨，不是读书的料。", optimistic: false },
    ],
  },
];

export interface StyleResult {
  byDimension: Record<StyleDimension, { optimistic: number; total: number }>;
  overall: number; // 0-100
}

export function scoreStyle(picks: boolean[]): StyleResult {
  const byDimension = Object.fromEntries(
    STYLE_DIMENSIONS.map(d => [d, { optimistic: 0, total: 0 }])
  ) as StyleResult["byDimension"];
  picks.forEach((optimistic, i) => {
    const item = STYLE_ITEMS[i];
    if (!item) return;
    byDimension[item.dimension].total++;
    if (optimistic) byDimension[item.dimension].optimistic++;
  });
  const done = picks.length || 1;
  const overall = Math.round((picks.filter(Boolean).length / done) * 100);
  return { byDimension, overall };
}

export function styleVerdict(overall: number): string {
  if (overall >= 78) return "你解释挫折的方式很有弹性——坏事在你这里是暂时的、局部的。守住它。";
  if (overall >= 45) return "你在乐观与苛责之间摇摆。留意那些「永远」「全都」「都怪我」，它们多半不是事实。";
  return "你习惯把一次挫折读成永久的判决。试着只描述发生了什么，不加结论——这是可以练习的。";
}
