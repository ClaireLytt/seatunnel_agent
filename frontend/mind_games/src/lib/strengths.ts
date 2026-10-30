// VIA character strengths, abridged — twelve either/or cards over twelve of
// Seligman & Peterson's 24 strengths; each strength appears on two cards.

import type { Bi } from './optimism'

export const STRENGTHS = [
  'curiosity',
  'perseverance',
  'kindness',
  'humor',
  'gratitude',
  'hope',
  'creativity',
  'honesty',
  'prudence',
  'zest',
  'love_of_learning',
  'appreciation_of_beauty',
] as const
export type Strength = (typeof STRENGTHS)[number]

export const STRENGTH_LABEL: Record<Strength, { zh: string; en: string; desc: Bi }> = {
  curiosity: {
    zh: '好奇心',
    en: 'Curiosity',
    desc: {
      zh: '对世界保持新鲜的疑问，愿意探索与尝试。',
      en: 'You keep fresh questions about the world, ready to explore and try.',
    },
  },
  perseverance: {
    zh: '坚毅',
    en: 'Perseverance',
    desc: {
      zh: '开始的事情会做完，困难只是过程的一部分。',
      en: 'What you start, you finish; difficulty is just part of the process.',
    },
  },
  kindness: {
    zh: '善良',
    en: 'Kindness',
    desc: {
      zh: '乐于照顾与帮助他人，哪怕没有回报。',
      en: 'You care for and help others, even with nothing in return.',
    },
  },
  humor: {
    zh: '幽默',
    en: 'Humor',
    desc: {
      zh: '擅长把轻盈带给别人，在沉重处看见可笑的一面。',
      en: 'You bring lightness to others and find the funny side of heavy moments.',
    },
  },
  gratitude: {
    zh: '感恩',
    en: 'Gratitude',
    desc: {
      zh: '留意并珍视发生在自己身上的好事。',
      en: 'You notice and treasure the good things that happen to you.',
    },
  },
  hope: {
    zh: '希望',
    en: 'Hope',
    desc: {
      zh: '相信未来值得期待，并愿意为之努力。',
      en: 'You believe the future is worth expecting, and work toward it.',
    },
  },
  creativity: {
    zh: '创造力',
    en: 'Creativity',
    desc: {
      zh: '喜欢用新的方式思考和做事。',
      en: 'You like thinking and doing things in new ways.',
    },
  },
  honesty: {
    zh: '诚实',
    en: 'Honesty',
    desc: {
      zh: '以真实的面目生活，言行一致。',
      en: 'You live as your true self; your words and actions align.',
    },
  },
  prudence: {
    zh: '审慎',
    en: 'Prudence',
    desc: {
      zh: '三思而后行，不为短利冒不值的险。',
      en: 'You think before acting and take no cheap risks for quick gains.',
    },
  },
  zest: {
    zh: '热情',
    en: 'Zest',
    desc: {
      zh: '带着能量投入生活，把每天过得有声有色。',
      en: 'You throw energy into living and make each day vivid.',
    },
  },
  love_of_learning: {
    zh: '好学',
    en: 'Love of Learning',
    desc: {
      zh: '掌握新知识与技能本身就让你快乐。',
      en: 'Mastering new knowledge and skills is itself a joy for you.',
    },
  },
  appreciation_of_beauty: {
    zh: '审美',
    en: 'Appreciation of Beauty',
    desc: {
      zh: '会为自然、艺术或他人的卓越而驻足动容。',
      en: 'You pause, moved, before nature, art, or excellence in others.',
    },
  },
}

export interface StrengthCard {
  a: { text: Bi; strength: Strength }
  b: { text: Bi; strength: Strength }
}

export const STRENGTH_CARDS: StrengthCard[] = [
  {
    a: {
      text: {
        zh: '遇到不懂的东西，我会忍不住查个究竟。',
        en: 'When I meet something I do not understand, I have to look it up.',
      },
      strength: 'curiosity',
    },
    b: {
      text: {
        zh: '定下的目标，我会一步步啃完。',
        en: 'A goal once set, I chew through step by step.',
      },
      strength: 'perseverance',
    },
  },
  {
    a: {
      text: {
        zh: '朋友难过时，我总是第一个陪着的人。',
        en: 'When a friend is down, I am the first one there.',
      },
      strength: 'kindness',
    },
    b: {
      text: {
        zh: '气氛僵住时，我总能说句话让大家笑出来。',
        en: 'When the room freezes, I can always say something that gets a laugh.',
      },
      strength: 'humor',
    },
  },
  {
    a: {
      text: {
        zh: '我常常觉得自己已经拥有很多。',
        en: 'I often feel I already have plenty.',
      },
      strength: 'gratitude',
    },
    b: {
      text: {
        zh: '再糟的处境，我也相信会好起来。',
        en: 'However bad things get, I believe they will turn.',
      },
      strength: 'hope',
    },
  },
  {
    a: {
      text: {
        zh: '我喜欢把事情做得和别人不一样。',
        en: 'I like doing things differently from everyone else.',
      },
      strength: 'creativity',
    },
    b: {
      text: {
        zh: '我说的话，别人可以放心当真。',
        en: 'People can safely take my word at face value.',
      },
      strength: 'honesty',
    },
  },
  {
    a: {
      text: {
        zh: '做决定前，我习惯把后果想清楚。',
        en: 'Before deciding, I think the consequences through.',
      },
      strength: 'prudence',
    },
    b: {
      text: {
        zh: '我做事情总是带着一股劲儿。',
        en: 'Whatever I do, I do with drive.',
      },
      strength: 'zest',
    },
  },
  {
    a: {
      text: {
        zh: '学会一样新东西会让我开心很久。',
        en: 'Learning something new keeps me happy for a long while.',
      },
      strength: 'love_of_learning',
    },
    b: {
      text: {
        zh: '一片好看的晚霞能让我停下脚步。',
        en: 'A beautiful sunset can stop me in my tracks.',
      },
      strength: 'appreciation_of_beauty',
    },
  },
  {
    a: {
      text: {
        zh: '我常问「为什么」和「如果换一种呢」。',
        en: 'I keep asking "why" and "what if we tried it another way".',
      },
      strength: 'curiosity',
    },
    b: {
      text: {
        zh: '我有一些坚持了很多年的小习惯。',
        en: 'I have small habits I have kept for many years.',
      },
      strength: 'perseverance',
    },
  },
  {
    a: {
      text: {
        zh: '我会记得别人随口提过的需要。',
        en: 'I remember needs people mention only in passing.',
      },
      strength: 'kindness',
    },
    b: {
      text: {
        zh: '我擅长自嘲，不怕拿自己开玩笑。',
        en: 'I am good at laughing at myself and do not mind the joke.',
      },
      strength: 'humor',
    },
  },
  {
    a: {
      text: {
        zh: '我常把「谢谢」说出口，也真的这么想。',
        en: 'I say "thank you" out loud, and I mean it.',
      },
      strength: 'gratitude',
    },
    b: {
      text: {
        zh: '我喜欢为还没发生的事做打算。',
        en: 'I like making plans for things that have not happened yet.',
      },
      strength: 'hope',
    },
  },
  {
    a: {
      text: {
        zh: '我脑子里常冒出奇怪但有趣的点子。',
        en: 'Odd but interesting ideas keep popping into my head.',
      },
      strength: 'creativity',
    },
    b: {
      text: {
        zh: '即使说实话会吃亏，我也不太会撒谎。',
        en: 'Even when honesty costs me, I am a poor liar.',
      },
      strength: 'honesty',
    },
  },
  {
    a: {
      text: {
        zh: '朋友说我是那个「靠谱、不冲动」的人。',
        en: 'Friends call me the "reliable, never rash" one.',
      },
      strength: 'prudence',
    },
    b: {
      text: {
        zh: '早上醒来，我通常对今天有点期待。',
        en: 'Waking up, I usually look forward to the day a little.',
      },
      strength: 'zest',
    },
  },
  {
    a: {
      text: {
        zh: '我书签里存着一堆「改天研究」的教程。',
        en: 'My bookmarks hold a pile of "study this someday" tutorials.',
      },
      strength: 'love_of_learning',
    },
    b: {
      text: {
        zh: '我会专门绕路去看一棵开花的树。',
        en: 'I will take a detour just to see a tree in bloom.',
      },
      strength: 'appreciation_of_beauty',
    },
  },
]

export function topStrengths(picks: Strength[], n = 3): { strength: Strength; count: number }[] {
  const tally = new Map<Strength, number>()
  for (const s of picks) tally.set(s, (tally.get(s) ?? 0) + 1)
  return [...tally.entries()]
    .map(([strength, count]) => ({ strength, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, n)
}
