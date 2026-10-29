import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Mind Games',
      subtitle:
        'Three positive-psychology exercises, fully in the browser: ' +
        'the learned-optimism cards, the VIA signature-strengths picker ' +
        'and the five PERMA questions. Nothing leaves this page.',
      tab_optimism: 'Learned Optimism',
      tab_strengths: 'Signature Strengths',
      tab_questions: 'Five Questions',
      progress: 'Question',
      back: 'Back',
      again: 'Play again',
      reveal: 'Reveal my pillars',
      your_top: 'Your top strengths',
      verdict_label: 'Reading',
      optimism_hint: 'Which first reaction is closer to yours?',
      strengths_hint: 'Which line sounds more like you?',
      questions_hint: 'One short line per question is enough.',
      answer_ph: 'One line is enough',
      last_vs: 'last time {{a}} → this time {{b}}',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '心理小游戏',
      subtitle:
        '三个积极心理学练习，全部在浏览器本地运行：乐观解释风格卡片、' +
        'VIA 品格优势二选一、PERMA 五问画像。数据不离开这个页面。',
      tab_optimism: '乐观解释风格',
      tab_strengths: '品格优势',
      tab_questions: '五个问题',
      progress: '第',
      back: '上一题',
      again: '再来一轮',
      reveal: '看看我的五个支柱',
      your_top: '你的签名优势',
      verdict_label: '解读',
      optimism_hint: '此刻你心里的第一反应更接近哪一句？',
      strengths_hint: '哪一句更像你？',
      questions_hint: '每题一句话即可。',
      answer_ph: '一句话即可',
      last_vs: '上次 {{a}} → 这次 {{b}}',
      home: '首页',
    },
  },
}

export default initI18n(resources)
