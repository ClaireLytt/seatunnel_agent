import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'SLA Board',
      subtitle:
        'Did the task finish by its deadline? Paste the completion ' +
        'records — per task the board scores attainment against the ' +
        'target, the lateness percentiles, and the miss streaks, with ' +
        'live streaks called out first. Times take HH:MM (25:30 works ' +
        'for past midnight) or ISO datetimes.',
      data_label: 'Completion records (task,date,deadline,finish)',
      data_ph: 'task,date,deadline,finish\ndws_orders,2026-10-30,07:00,07:20',
      target_label: 'Attainment target (0.5 - 1.0)',
      run_btn: 'Score board',
      clear_btn: 'Clear',
      empty_input: 'Paste the completion records first.',
      report_ph: '▶ Per-task attainment and findings appear here.',
      llm_label: 'LLM SLA update (needs an API key)',
      home: 'Home',
      running: 'Scoring…',
    },
  },
  zh: {
    translation: {
      title: 'SLA 达成看板',
      subtitle:
        '任务按时跑完了吗？粘贴完成记录 — 逐任务对照目标给出达成率、' +
        '迟到分位数与连续破线天数，正在破线的任务排最前。时间接受 ' +
        'HH:MM（过午夜可写 25:30）或 ISO 时间。',
      data_label: '完成记录（task,date,deadline,finish）',
      data_ph: 'task,date,deadline,finish\ndws_orders,2026-10-30,07:00,07:20',
      target_label: '达成率目标（0.5 - 1.0）',
      run_btn: '生成看板',
      clear_btn: '清空',
      empty_input: '请先粘贴完成记录。',
      report_ph: '▶ 逐任务达成与分级发现在此显示。',
      llm_label: 'LLM SLA 通报（需 API key）',
      home: '首页',
      running: '统计中…',
    },
  },
}

export default initI18n(resources)
