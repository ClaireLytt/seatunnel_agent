import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Distribution Drift',
      subtitle:
        'Paste the baseline and the current data samples (CSV with a ' +
        'header row, JSONL, or a sample-profile JSON) — columns come ' +
        'back compared side by side: mean shifts, null and unique-rate ' +
        'jumps, category share drift with the biggest movers, schema ' +
        'and kind changes, ranked by severity. No database connection.',
      baseline_label: 'Baseline sample',
      current_label: 'Current sample',
      data_ph: 'order_id,channel,amount\n1,app,100.0\n...',
      maxrows_label: 'Sample cap per side',
      run_btn: 'Compare',
      clear_btn: 'Clear',
      empty_input: 'Paste both samples first.',
      report_ph: '▶ Drift findings ranked by severity appear here.',
      llm_label: 'LLM drift note (needs an API key)',
      home: 'Home',
      running: 'Comparing…',
    },
  },
  zh: {
    translation: {
      title: '数据分布异常',
      subtitle:
        '粘贴基线与当前两份数据样本（CSV 带表头 / JSONL / 抽样剖析的 ' +
        'profile JSON）— 逐列对比返回：均值漂移、空值/唯一率突变、' +
        '类别占比漂移（附移动最大的类别）、schema 与类型变化，' +
        '按严重度排序。不连数据库。',
      baseline_label: '基线样本',
      current_label: '当前样本',
      data_ph: 'order_id,channel,amount\n1,app,100.0\n...',
      maxrows_label: '每侧抽样上限',
      run_btn: '对比',
      clear_btn: '清空',
      empty_input: '请先粘贴两份样本。',
      report_ph: '▶ 按严重度排序的漂移发现在此显示。',
      llm_label: 'LLM 漂移通报（需 API key）',
      home: '首页',
      running: '对比中…',
    },
  },
}

export default initI18n(resources)
