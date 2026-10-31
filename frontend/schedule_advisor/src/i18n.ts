import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Schedule Advisor',
      subtitle:
        'Will the batch make its SLA, and who can move? Paste the day ' +
        'plan (JSON with day_start, task durations and dependencies, an ' +
        'optional SLA task and deadline) — back come the earliest ' +
        'timeline, the SLA margin with thin/negative verdicts, the ' +
        'critical path, per-task slack and the peak-parallelism window ' +
        'with the tasks movable out of it. Feed p95 durations. No ' +
        'scheduler connection.',
      plan_label: 'Day plan (JSON)',
      plan_ph: '{"day_start":"00:30","sla":{"task":"ads_kpi","deadline":"07:00"},"tasks":[...]}',
      run_btn: 'Advise',
      clear_btn: 'Clear',
      empty_input: 'Paste the plan first.',
      report_ph: '▶ Timeline, critical path and margins appear here.',
      llm_label: 'LLM schedule note (needs an API key)',
      home: 'Home',
      running: 'Advising…',
    },
  },
  zh: {
    translation: {
      title: '调度窗口优化',
      subtitle:
        '批次赶得上 SLA 吗、谁可以挪？粘贴一天的排程计划（JSON：' +
        'day_start、各任务时长与依赖、可选 SLA 任务与截止时间）— 返回' +
        '最早排程时间线、SLA 余量（偏薄/破线点名）、关键路径、各任务' +
        '松弛与并行峰值窗口及可错峰任务。时长建议喂 p95。不连调度器。',
      plan_label: '排程计划（JSON）',
      plan_ph: '{"day_start":"00:30","sla":{"task":"ads_kpi","deadline":"07:00"},"tasks":[...]}',
      run_btn: '给建议',
      clear_btn: '清空',
      empty_input: '请先粘贴计划。',
      report_ph: '▶ 时间线、关键路径与余量在此显示。',
      llm_label: 'LLM 排程通报（需 API key）',
      home: '首页',
      running: '计算中…',
    },
  },
}

export default initI18n(resources)
