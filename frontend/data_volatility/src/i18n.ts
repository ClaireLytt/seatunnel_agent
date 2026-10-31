import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Data Volatility',
      subtitle:
        'Paste metric time series (CSV with a date,metric,value header, ' +
        'or JSONL; several metrics in one paste) — surges and drops come ' +
        'back judged against a rolling median, plus level shifts, ' +
        'flatlines and date gaps, ranked by severity with the evidence ' +
        'numbers. No database connection.',
      series_label: 'Series rows (date,metric,value)',
      series_ph: 'date,metric,value\n2026-10-01,order_cnt,1020\n...',
      run_btn: 'Analyze',
      clear_btn: 'Clear',
      empty_input: 'Paste the series rows first.',
      report_ph: '▶ Surges, drops, shifts and gaps appear here.',
      llm_label: 'LLM volatility note (needs an API key)',
      trace_btn: 'Trace the top finding upstream',
      home: 'Home',
      running: 'Analyzing…',
    },
  },
  zh: {
    translation: {
      title: '数据波动分析',
      subtitle:
        '粘贴指标时间序列（CSV 表头 date,metric,value 或同字段 JSONL，' +
        '多指标共用一份）— 按滚动中位数判突增/突降，并检出水平位移、' +
        '走平与日期断档，按严重度排序附证据数字。不连数据库。',
      series_label: '序列行（date,metric,value）',
      series_ph: 'date,metric,value\n2026-10-01,order_cnt,1020\n...',
      run_btn: '分析',
      clear_btn: '清空',
      empty_input: '请先粘贴序列行。',
      report_ph: '▶ 突增/突降/位移/断档在此显示。',
      llm_label: 'LLM 波动通报（需 API key）',
      trace_btn: '把首个发现交给根因追踪',
      home: '首页',
      running: '分析中…',
    },
  },
}

export default initI18n(resources)
