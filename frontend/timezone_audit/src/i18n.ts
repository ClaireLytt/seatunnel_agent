import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Timezone Audit',
      subtitle:
        'A timestamp column can be wrong four ways no type checker ' +
        'sees: mixed explicit offsets, seconds beside milliseconds, the ' +
        '8-hour bimodal smell of UTC-vs-local, and sentinel years. ' +
        'Paste the rows — every timestamp column gets audited.',
      data_label: 'Data rows (CSV with header, or JSONL)',
      data_ph: 'created_at,event_ts\n2026-10-01T10:00:00+08:00,1730000001',
      run_btn: 'Audit timestamps',
      clear_btn: 'Clear',
      empty_input: 'Paste the data rows first.',
      report_ph: '▶ Per-column timestamp findings appear here.',
      llm_label: 'LLM normalization note (needs an API key)',
      home: 'Home',
      running: 'Auditing…',
    },
  },
  zh: {
    translation: {
      title: '时间戳体检',
      subtitle:
        '时间戳列有四种类型检查看不见的坏法：显式时区不一致、秒毫秒' +
        '混用、UTC/本地混用的 8 小时双峰、哨兵年份。粘贴数据行 — 逐个' +
        '时间戳列体检。',
      data_label: '数据行（CSV 带表头，或 JSONL）',
      data_ph: 'created_at,event_ts\n2026-10-01T10:00:00+08:00,1730000001',
      run_btn: '开始体检',
      clear_btn: '清空',
      empty_input: '请先粘贴数据行。',
      report_ph: '▶ 逐列时间戳发现在此显示。',
      llm_label: 'LLM 归一建议（需 API key）',
      home: '首页',
      running: '体检中…',
    },
  },
}

export default initI18n(resources)
