import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Data Repair',
      subtitle:
        'Paste CSV (header row) or JSONL data rows with the target table ' +
        'name — duplicates, high-null columns, numbers stored as text ' +
        'and format drift come back as copy-ready repair SQL: ROW_NUMBER ' +
        'dedup, COALESCE backfill, TRIM/LOWER standardization and ' +
        'cleanup casts. Placeholders stay for human decisions. No ' +
        'database connection.',
      data_label: 'Data rows (CSV or JSONL)',
      data_ph: 'event_id,user_id,amount\ne001,u001,100.0\n...',
      table_label: 'Target table',
      table_ph: 'e.g. dwd.pay_events',
      pk_label: 'Primary-key columns (comma-separated, optional)',
      pk_ph: 'e.g. event_id',
      biz_label: 'Business-key columns (comma-separated, optional)',
      biz_ph: 'e.g. user_id,action,amount',
      run_btn: 'Plan repairs',
      clear_btn: 'Clear',
      empty_input: 'Paste the data rows first.',
      report_ph: '▶ Ranked repair actions with SQL templates appear here.',
      llm_label: 'LLM repair note (needs an API key)',
      home: 'Home',
      running: 'Planning…',
    },
  },
  zh: {
    translation: {
      title: '一致性修复',
      subtitle:
        '粘贴 CSV（带表头）或 JSONL 数据行 + 目标表名 — 重复、高空值列、' +
        '存成文本的数值与格式漂移自动生成可复制的修复 SQL：ROW_NUMBER ' +
        '去重、COALESCE 回填、TRIM/LOWER 标准化与清洗转换；占位符留给' +
        '人工决策。不连数据库。',
      data_label: '数据行（CSV 或 JSONL）',
      data_ph: 'event_id,user_id,amount\ne001,u001,100.0\n...',
      table_label: '目标表',
      table_ph: '如 dwd.pay_events',
      pk_label: '主键列（逗号分隔，可选）',
      pk_ph: '如 event_id',
      biz_label: '业务键列（逗号分隔，可选）',
      biz_ph: '如 user_id,action,amount',
      run_btn: '生成修复方案',
      clear_btn: '清空',
      empty_input: '请先粘贴数据行。',
      report_ph: '▶ 按级别排序的修复动作与 SQL 模板在此显示。',
      llm_label: 'LLM 修复变更说明（需 API key）',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
