// VIA character strengths, abridged — twelve either/or cards over twelve of
// Seligman & Peterson's 24 strengths; each strength appears on two cards.

export const STRENGTHS = [
  "curiosity",
  "perseverance",
  "kindness",
  "humor",
  "gratitude",
  "hope",
  "creativity",
  "honesty",
  "prudence",
  "zest",
  "love_of_learning",
  "appreciation_of_beauty",
] as const;
export type Strength = (typeof STRENGTHS)[number];

export const STRENGTH_LABEL: Record<Strength, { zh: string; desc: string }> = {
  curiosity:              { zh: "好奇心",   desc: "对世界保持新鲜的疑问，愿意探索与尝试。" },
  perseverance:           { zh: "坚毅",     desc: "开始的事情会做完，困难只是过程的一部分。" },
  kindness:               { zh: "善良",     desc: "乐于照顾与帮助他人，哪怕没有回报。" },
  humor:                  { zh: "幽默",     desc: "擅长把轻盈带给别人，在沉重处看见可笑的一面。" },
  gratitude:              { zh: "感恩",     desc: "留意并珍视发生在自己身上的好事。" },
  hope:                   { zh: "希望",     desc: "相信未来值得期待，并愿意为之努力。" },
  creativity:             { zh: "创造力",   desc: "喜欢用新的方式思考和做事。" },
  honesty:                { zh: "诚实",     desc: "以真实的面目生活，言行一致。" },
  prudence:               { zh: "审慎",     desc: "三思而后行，不为短利冒不值的险。" },
  zest:                   { zh: "热情",     desc: "带着能量投入生活，把每天过得有声有色。" },
  love_of_learning:       { zh: "好学",     desc: "掌握新知识与技能本身就让你快乐。" },
  appreciation_of_beauty: { zh: "审美",     desc: "会为自然、艺术或他人的卓越而驻足动容。" },
};

export interface StrengthCard {
  a: { text: string; strength: Strength };
  b: { text: string; strength: Strength };
}

export const STRENGTH_CARDS: StrengthCard[] = [
  {
    a: { text: "遇到不懂的东西，我会忍不住查个究竟。", strength: "curiosity" },
    b: { text: "定下的目标，我会一步步啃完。", strength: "perseverance" },
  },
  {
    a: { text: "朋友难过时，我总是第一个陪着的人。", strength: "kindness" },
    b: { text: "气氛僵住时，我总能说句话让大家笑出来。", strength: "humor" },
  },
  {
    a: { text: "我常常觉得自己已经拥有很多。", strength: "gratitude" },
    b: { text: "再糟的处境，我也相信会好起来。", strength: "hope" },
  },
  {
    a: { text: "我喜欢把事情做得和别人不一样。", strength: "creativity" },
    b: { text: "我说的话，别人可以放心当真。", strength: "honesty" },
  },
  {
    a: { text: "做决定前，我习惯把后果想清楚。", strength: "prudence" },
    b: { text: "我做事情总是带着一股劲儿。", strength: "zest" },
  },
  {
    a: { text: "学会一样新东西会让我开心很久。", strength: "love_of_learning" },
    b: { text: "一片好看的晚霞能让我停下脚步。", strength: "appreciation_of_beauty" },
  },
  {
    a: { text: "我常问「为什么」和「如果换一种呢」。", strength: "curiosity" },
    b: { text: "我有一些坚持了很多年的小习惯。", strength: "perseverance" },
  },
  {
    a: { text: "我会记得别人随口提过的需要。", strength: "kindness" },
    b: { text: "我擅长自嘲，不怕拿自己开玩笑。", strength: "humor" },
  },
  {
    a: { text: "我常把「谢谢」说出口，也真的这么想。", strength: "gratitude" },
    b: { text: "我喜欢为还没发生的事做打算。", strength: "hope" },
  },
  {
    a: { text: "我脑子里常冒出奇怪但有趣的点子。", strength: "creativity" },
    b: { text: "即使说实话会吃亏，我也不太会撒谎。", strength: "honesty" },
  },
  {
    a: { text: "朋友说我是那个「靠谱、不冲动」的人。", strength: "prudence" },
    b: { text: "早上醒来，我通常对今天有点期待。", strength: "zest" },
  },
  {
    a: { text: "我书签里存着一堆「改天研究」的教程。", strength: "love_of_learning" },
    b: { text: "我会专门绕路去看一棵开花的树。", strength: "appreciation_of_beauty" },
  },
];

export function topStrengths(picks: Strength[], n = 3): { strength: Strength; count: number }[] {
  const tally = new Map<Strength, number>();
  for (const s of picks) tally.set(s, (tally.get(s) ?? 0) + 1);
  return [...tally.entries()]
    .map(([strength, count]) => ({ strength, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, n);
}
