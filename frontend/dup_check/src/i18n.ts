import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Duplicate Check',
      subtitle:
        'Paste CSV (header row) or JSONL data rows and optionally declare ' +
        'the primary-key and business-event key columns — duplicates come ' +
        'back on three layers (identical rows, repeated keys, repeated ' +
        'events) with row spans and the differing columns that locate ' +
        'the source. No database connection.',
      data_label: 'Data rows (CSV or JSONL)',
      data_ph: 'event_id,user_id,amount\ne001,u001,100.0\n...',
      pk_label: 'Primary-key columns (comma-separated, optional)',
      pk_ph: 'e.g. event_id',
      biz_label: 'Business-key columns (comma-separated, optional)',
      biz_ph: 'e.g. user_id,action,amount',
      run_btn: 'Check',
      clear_btn: 'Clear',
      empty_input: 'Paste the data rows first.',
      report_ph: '▶ Duplicate groups with row spans appear here.',
      llm_label: 'LLM dedup note (needs an API key)',
      home: 'Home',
      running: 'Checking…',
    },
  },
  zh: {
    translation: {
      title: '数据重复检测',
      subtitle:
        '粘贴 CSV（带表头）或 JSONL 数据行，可选声明主键列与业务键列 — ' +
        '三层返回重复组（全行重复、主键重复、业务事件重复），每组带首末' +
        '行号与差异列，差异列指向重复来源。不连数据库。',
      data_label: '数据行（CSV 或 JSONL）',
      data_ph: 'event_id,user_id,amount\ne001,u001,100.0\n...',
      pk_label: '主键列（逗号分隔，可选）',
      pk_ph: '如 event_id',
      biz_label: '业务键列（逗号分隔，可选）',
      biz_ph: '如 user_id,action,amount',
      run_btn: '检测',
      clear_btn: '清空',
      empty_input: '请先粘贴数据行。',
      report_ph: '▶ 带首末行号的重复组在此显示。',
      llm_label: 'LLM 去重处置通报（需 API key）',
      home: '首页',
      running: '检测中…',
    },
  },
}

export default initI18n(resources)
