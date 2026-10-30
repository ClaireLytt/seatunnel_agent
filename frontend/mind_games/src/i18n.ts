import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Mind Games',
      subtitle:
        'Positive-psychology exercises, fully in the browser: the ' +
        'learned-optimism cards, the VIA strengths picker, the five PERMA ' +
        'questions, three good things with a lamp, and a 4-7-8 breathing ' +
        'window. Nothing leaves this page.',
      tab_optimism: 'Learned Optimism',
      tab_strengths: 'Signature Strengths',
      tab_questions: 'Five Questions',
      tab_three: 'Three Good Things',
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
      ledger: 'The ledger',
      three_hint:
        "Seligman's evening ritual: three things that went well tonight, " +
        'and why each one happened. Once a day; the lamp remembers.',
      what_ph: 'What went well…',
      why_ph: 'Why did it happen…',
      save_three: 'Set down tonight',
      today_done: 'Tonight is written. The lamp stays lit — come back tomorrow.',
      lamp_streak: '{{n}} consecutive evenings',
      lamp_first: 'The first evening lights the lamp.',
      recent_evenings: 'Past evenings',
      from_corner: 'From the hall notebook',
      corner_note: 'Entries also land in the notebook on the landing page.',
      tab_breath: 'Breathing',
      breath_hint:
        'The 4-7-8 pattern: in through the nose for four, hold for seven, ' +
        'out through the mouth for eight. Three rounds settle the evening.',
      breath_in: 'Breathe in',
      breath_hold: 'Hold',
      breath_out: 'Breathe out',
      breath_start: 'Begin',
      breath_again: 'Once more',
      breath_round: 'Round {{i}} of {{n}}',
      breath_done: 'Three rounds, done. The room is quieter.',
      breath_write: 'Set this moment down as a good thing',
      suitcase_export: 'Pack the suitcase',
      suitcase_import: 'Unpack a suitcase',
      suitcase_note:
        'Everything here lives in this browser. The suitcase carries it: ' +
        'export a file, unpack it elsewhere — merged, never deleted.',
      suitcase_merged: 'Unpacked: {{n}} records merged.',
      suitcase_bad: 'That file is not a suitcase from this page.',
    },
  },
  zh: {
    translation: {
      title: '心理小游戏',
      subtitle:
        '积极心理学练习，全部在浏览器本地运行：乐观解释风格卡片、' +
        'VIA 品格优势二选一、PERMA 五问画像、三件好事与油灯、' +
        '4-7-8 呼吸窗。数据不离开这个页面。',
      tab_optimism: '乐观解释风格',
      tab_strengths: '品格优势',
      tab_questions: '五个问题',
      tab_three: '三件好事',
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
      ledger: '档案台账',
      three_hint:
        '塞利格曼的晚间仪式：写下今晚进展顺利的三件事，以及它们为什么发生。' +
        '一天一次，油灯会记得。',
      what_ph: '什么事进展顺利…',
      why_ph: '它为什么会发生…',
      save_three: '落笔今晚',
      today_done: '今晚已写下。灯亮着——明晚再来。',
      lamp_streak: '连记 {{n}} 晚',
      lamp_first: '第一晚会点亮这盏灯。',
      recent_evenings: '过去的夜晚',
      from_corner: '来自门厅笔记本',
      corner_note: '写下的好事也会落到首页角落的笔记本里。',
      tab_breath: '呼吸窗',
      breath_hint: '4-7-8 呼吸:用鼻吸气四拍,屏息七拍,用嘴呼气八拍。三轮,把晚上安顿下来。',
      breath_in: '吸气',
      breath_hold: '屏息',
      breath_out: '呼气',
      breath_start: '开始',
      breath_again: '再来一次',
      breath_round: '第 {{i}} / {{n}} 轮',
      breath_done: '三轮结束。房间安静了一些。',
      breath_write: '把此刻写成一件好事',
      suitcase_export: '收拾行囊',
      suitcase_import: '打开行囊',
      suitcase_note:
        '这里的一切都住在当前浏览器。行囊负责搬家:导出一个文件,' + '在别处打开——只合并,不删除。',
      suitcase_merged: '已打开:合并 {{n}} 条记录。',
      suitcase_bad: '这不是本页的行囊文件。',
    },
  },
}

export default initI18n(resources)
