import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Metric Attribution',
      subtitle:
        'The metric moved — which dimension value did it? Paste the ' +
        'baseline and current result sets sliced by dimensions, name ' +
        'the dimension and metric columns — the change decomposes ' +
        'exactly into per-value contributions with shares, plus ' +
        'verdicts for the top contributor, single-value concentration ' +
        'and offsetting mix shifts. No database connection.',
      baseline_label: 'Baseline result set',
      current_label: 'Current result set',
      data_ph: 'dt,channel,gmv\n2026-10-29,app,50000\n...',
      dims_label: 'Dimension columns (comma-separated)',
      dims_ph: 'e.g. channel,region',
      metric_label: 'Metric column',
      metric_ph: 'e.g. gmv',
      run_btn: 'Attribute',
      clear_btn: 'Clear',
      empty_input: 'Paste both sides and name the columns first.',
      report_ph: '▶ Per-value contributions and verdicts appear here.',
      llm_label: 'LLM attribution reply (needs an API key)',
      home: 'Home',
      running: 'Attributing…',
    },
  },
  zh: {
    translation: {
      title: '指标异动归因',
      subtitle:
        '指标动了 — 哪个维度的哪个值干的？粘贴基线与当前两份按维度切分' +
        '的结果集，填维度列与指标列 — 变动精确可加地分解到每个取值' +
        '（含占比、新出现/消失），并判定头号贡献、单点集中与涨跌对冲。' +
        '不连数据库。',
      baseline_label: '基线结果集',
      current_label: '当前结果集',
      data_ph: 'dt,channel,gmv\n2026-10-29,app,50000\n...',
      dims_label: '维度列（逗号分隔）',
      dims_ph: '如 channel,region',
      metric_label: '指标列',
      metric_ph: '如 gmv',
      run_btn: '归因',
      clear_btn: '清空',
      empty_input: '请先粘贴两侧并填列名。',
      report_ph: '▶ 逐值贡献与判定在此显示。',
      llm_label: 'LLM 归因回复（需 API key）',
      home: '首页',
      running: '归因中…',
    },
  },
}

export default initI18n(resources)
