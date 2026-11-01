import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Capacity Forecast',
      subtitle:
        'When does the storage run out? Paste the size series (CSV with ' +
        'a date,metric,value header; metric = table, value = GB or ' +
        'rows) and the quota — back come the exhaustion date from ' +
        'recent slopes (linear, stated openly), 90/30-day alarms, the ' +
        'top growers with their share, and the shrinking metrics. No ' +
        'storage connection.',
      series_label: 'Storage series (date,metric,value)',
      series_ph: 'date,metric,value\n2026-10-30,ods.click_log,740\n...',
      quota_label: 'Quota (same unit as the values)',
      run_btn: 'Forecast',
      clear_btn: 'Clear',
      empty_input: 'Paste the series and set the quota first.',
      report_ph: '▶ Exhaustion date and top growers appear here.',
      llm_label: 'LLM capacity note (needs an API key)',
      home: 'Home',
      running: 'Forecasting…',
    },
  },
  zh: {
    translation: {
      title: '容量耗尽预测',
      subtitle:
        '存储什么时候爆？粘贴大小序列（CSV 表头 date,metric,value；' +
        'metric=表名,value=GB 或行数）+ 配额 — 按近期斜率外推耗尽日期' +
        '（线性、明示假设）、90/30 天告警、增长大户及其占比、在缩小的' +
        '指标。不连存储。',
      series_label: '存储序列（date,metric,value）',
      series_ph: 'date,metric,value\n2026-10-30,ods.click_log,740\n...',
      quota_label: '配额（与数值同单位）',
      run_btn: '预测',
      clear_btn: '清空',
      empty_input: '请先粘贴序列并填配额。',
      report_ph: '▶ 耗尽日期与增长大户在此显示。',
      llm_label: 'LLM 容量通报（需 API key）',
      home: '首页',
      running: '预测中…',
    },
  },
}

export default initI18n(resources)
