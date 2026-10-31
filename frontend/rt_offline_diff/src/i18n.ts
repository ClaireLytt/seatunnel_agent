import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'RT-Offline Diff',
      subtitle:
        'Do realtime and offline agree? Paste both result sets (CSV ' +
        'with a header, or JSONL) plus the key columns and a tolerance ' +
        '— rows come back key-aligned: missing keys on either side, the ' +
        'worst over-tolerance mismatches, and a systematic-bias verdict ' +
        'per metric (realtime lower → late data; higher → duplicate ' +
        'consumption). No database connection.',
      rt_label: 'Realtime result set',
      off_label: 'Offline result set',
      data_ph: 'dt,channel,order_cnt,gmv\n2026-10-30,app,980,97500.0',
      keys_label: 'Key columns (comma-separated)',
      keys_ph: 'e.g. dt,channel',
      tol_label: 'Tolerance %',
      run_btn: 'Compare',
      clear_btn: 'Clear',
      empty_input: 'Paste both result sets and the keys first.',
      report_ph: '▶ Missing keys, mismatches and bias verdicts appear here.',
      llm_label: 'LLM reconciliation note (needs an API key)',
      home: 'Home',
      running: 'Comparing…',
    },
  },
  zh: {
    translation: {
      title: '实时离线核对',
      subtitle:
        '实时和离线对得上吗？粘贴两份结果集（CSV 带表头或 JSONL）+ 键列 ' +
        '+ 容差 — 按键对齐返回：双侧缺失键、超容差差异明细（差距大在前）' +
        '与每个指标的系统性偏差判定（实时偏低 → 迟到数据；偏高 → 重复' +
        '消费）。不连库。',
      rt_label: '实时结果集',
      off_label: '离线结果集',
      data_ph: 'dt,channel,order_cnt,gmv\n2026-10-30,app,980,97500.0',
      keys_label: '键列（逗号分隔）',
      keys_ph: '如 dt,channel',
      tol_label: '容差 %',
      run_btn: '核对',
      clear_btn: '清空',
      empty_input: '请先粘贴两份结果集并填键列。',
      report_ph: '▶ 缺失键、超差明细与偏差判定在此显示。',
      llm_label: 'LLM 核对通报（需 API key）',
      home: '首页',
      running: '核对中…',
    },
  },
}

export default initI18n(resources)
