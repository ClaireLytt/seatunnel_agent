// Learned Optimism — Seligman's ABC explanatory-style exercise as a small
// deterministic card game. Three dimensions, three cards each.

export type Lang = 'zh' | 'en'
export type Bi = Record<Lang, string>

export const STYLE_DIMENSIONS = ['permanence', 'pervasiveness', 'personalization'] as const
export type StyleDimension = (typeof STYLE_DIMENSIONS)[number]

export const STYLE_LABEL: Record<StyleDimension, { zh: string; en: string }> = {
  permanence: { zh: '永久性', en: 'Permanence' },
  pervasiveness: { zh: '普遍性', en: 'Pervasiveness' },
  personalization: { zh: '个人化', en: 'Personalization' },
}

export interface StyleItem {
  situation: Bi
  dimension: StyleDimension
  // exactly two readings of the same setback; `optimistic` marks the resilient one
  options: { text: Bi; optimistic: boolean }[]
}

export const STYLE_ITEMS: StyleItem[] = [
  {
    situation: {
      zh: '面试结束后，对方说「我们会再联系你」，然后杳无音信。',
      en: 'After the interview they said "we will be in touch" — then silence.',
    },
    dimension: 'permanence',
    options: [
      {
        text: {
          zh: '我大概永远过不了面试这一关。',
          en: 'I will probably never get past interviews.',
        },
        optimistic: false,
      },
      {
        text: {
          zh: '这一场没对上，下一场重新来。',
          en: 'This one was not a match; the next is a fresh start.',
        },
        optimistic: true,
      },
    ],
  },
  {
    situation: {
      zh: '你精心准备的晚餐烧糊了。',
      en: 'The dinner you prepared so carefully got burnt.',
    },
    dimension: 'permanence',
    options: [
      {
        text: {
          zh: '今天手气不好，下次换个火候。',
          en: 'Bad luck tonight — next time, different heat.',
        },
        optimistic: true,
      },
      {
        text: {
          zh: '我做饭从来就没成功过。',
          en: 'My cooking has never once worked out.',
        },
        optimistic: false,
      },
    ],
  },
  {
    situation: {
      zh: '坚持了两周的晨跑，这周一天都没去。',
      en: 'Two weeks of morning runs, and this week you skipped every day.',
    },
    dimension: 'permanence',
    options: [
      {
        text: {
          zh: '我总是半途而废，这次也一样。',
          en: 'I always quit halfway — this time is no different.',
        },
        optimistic: false,
      },
      {
        text: {
          zh: '这周太累了，下周一再捡起来。',
          en: 'This week was exhausting; I pick it up again on Monday.',
        },
        optimistic: true,
      },
    ],
  },
  {
    situation: {
      zh: '你在会议上说错了一个数据，被当场指出。',
      en: 'You quoted a wrong figure in a meeting and were corrected on the spot.',
    },
    dimension: 'pervasiveness',
    options: [
      {
        text: {
          zh: '一个数字记岔了，更正就是。',
          en: 'One number misremembered — correct it and move on.',
        },
        optimistic: true,
      },
      {
        text: {
          zh: '我整个人都不适合这份工作。',
          en: 'I am simply not cut out for this job at all.',
        },
        optimistic: false,
      },
    ],
  },
  {
    situation: {
      zh: '朋友聚会上，你讲的笑话没人笑。',
      en: 'At a gathering, your joke landed to silence.',
    },
    dimension: 'pervasiveness',
    options: [
      {
        text: {
          zh: '我是个无趣的人，社交一塌糊涂。',
          en: 'I am a boring person and hopeless at socializing.',
        },
        optimistic: false,
      },
      {
        text: {
          zh: '这个梗没接住而已，话题继续。',
          en: 'That one just did not land — on with the conversation.',
        },
        optimistic: true,
      },
    ],
  },
  {
    situation: {
      zh: '你养的绿萝黄了一半叶子。',
      en: 'Half the leaves on your pothos have turned yellow.',
    },
    dimension: 'pervasiveness',
    options: [
      {
        text: {
          zh: '浇水的节奏不对，调一调。',
          en: 'The watering rhythm is off — adjust it.',
        },
        optimistic: true,
      },
      {
        text: {
          zh: '我什么都养不活，什么都照顾不好。',
          en: 'I cannot keep anything alive or take care of anything.',
        },
        optimistic: false,
      },
    ],
  },
  {
    situation: {
      zh: '深夜给朋友发的消息，第二天中午还没回。',
      en: 'The message you sent a friend late at night is still unanswered by noon.',
    },
    dimension: 'personalization',
    options: [
      {
        text: {
          zh: '肯定是我说错了什么话让人烦了。',
          en: 'I must have said something that annoyed them.',
        },
        optimistic: false,
      },
      {
        text: {
          zh: '人们都很忙，未必和我有关。',
          en: 'People are busy; it may have nothing to do with me.',
        },
        optimistic: true,
      },
    ],
  },
  {
    situation: {
      zh: '小组项目没有按期完成。',
      en: 'The group project missed its deadline.',
    },
    dimension: 'personalization',
    options: [
      {
        text: {
          zh: '进度受很多环节影响，不全在我。',
          en: 'Many moving parts shaped the schedule — not all of it was mine.',
        },
        optimistic: true,
      },
      {
        text: {
          zh: '都怪我拖累了所有人。',
          en: 'It is my fault for dragging everyone down.',
        },
        optimistic: false,
      },
    ],
  },
  {
    situation: {
      zh: '考试成绩比预期低了不少。',
      en: 'Your exam score came back well below what you expected.',
    },
    dimension: 'personalization',
    options: [
      {
        text: {
          zh: '这次题目偏，准备方向也可以再调。',
          en: 'The questions were off-beat, and my prep can be re-aimed.',
        },
        optimistic: true,
      },
      {
        text: {
          zh: '是我太笨，不是读书的料。',
          en: 'I am just too slow — studying is not for me.',
        },
        optimistic: false,
      },
    ],
  },
]

export interface StyleResult {
  byDimension: Record<StyleDimension, { optimistic: number; total: number }>
  overall: number // 0-100
}

export function scoreStyle(picks: boolean[]): StyleResult {
  const byDimension = Object.fromEntries(
    STYLE_DIMENSIONS.map((d) => [d, { optimistic: 0, total: 0 }]),
  ) as StyleResult['byDimension']
  picks.forEach((optimistic, i) => {
    const item = STYLE_ITEMS[i]
    if (!item) return
    byDimension[item.dimension].total++
    if (optimistic) byDimension[item.dimension].optimistic++
  })
  const done = picks.length || 1
  const overall = Math.round((picks.filter(Boolean).length / done) * 100)
  return { byDimension, overall }
}

const VERDICTS: { min: number; text: Bi }[] = [
  {
    min: 78,
    text: {
      zh: '你解释挫折的方式很有弹性——坏事在你这里是暂时的、局部的。守住它。',
      en: 'Your way of explaining setbacks is resilient — bad things stay temporary and local with you. Hold on to that.',
    },
  },
  {
    min: 45,
    text: {
      zh: '你在乐观与苛责之间摇摆。留意那些「永远」「全都」「都怪我」，它们多半不是事实。',
      en: 'You swing between optimism and self-blame. Watch for "always", "everything", "all my fault" — they are rarely the facts.',
    },
  },
  {
    min: 0,
    text: {
      zh: '你习惯把一次挫折读成永久的判决。试着只描述发生了什么，不加结论——这是可以练习的。',
      en: 'You tend to read one setback as a permanent verdict. Try describing only what happened, without the conclusion — this can be practiced.',
    },
  },
]

export function styleVerdict(overall: number, lang: Lang = 'zh'): string {
  const v = VERDICTS.find((x) => overall >= x.min) ?? VERDICTS[VERDICTS.length - 1]
  return v.text[lang]
}
