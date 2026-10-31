import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Quality Trace',
      subtitle:
        'A table went wrong — who upstream did it? Paste the pipeline ' +
        'SQL scripts plus the polluted table (optionally the column and ' +
        'a one-line symptom): the ancestors come back ranked as ' +
        'suspects, with the mutation points (SUM/CAST/CASE) on the taint ' +
        'path and a copy-ready verification SQL each. No database ' +
        'connection.',
      sql_label: 'Pipeline SQL scripts',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      table_label: 'Polluted table',
      table_ph: 'e.g. dws.orders_daily',
      column_label: 'Polluted column (optional)',
      column_ph: 'e.g. gmv',
      symptom_label: 'Symptom (optional)',
      symptom_ph: 'e.g. gmv doubled since 10-05',
      run_btn: 'Trace',
      clear_btn: 'Clear',
      empty_input: 'Paste the SQL and name the polluted table first.',
      report_ph: '▶ Ranked suspects with verification SQL appear here.',
      llm_label: 'LLM trace note (needs an API key)',
      home: 'Home',
      running: 'Tracing…',
    },
  },
  zh: {
    translation: {
      title: '质量根因追踪',
      subtitle:
        '表出问题了 — 上游谁干的？粘贴流水线 SQL 脚本 + 出问题的表' +
        '（可选列与一句话症状）：上游按嫌疑分排行返回，附污染路径上的' +
        '变换点（SUM/CAST/CASE）与每个嫌疑可直接运行的验证 SQL。' +
        '不连数据库。',
      sql_label: '流水线 SQL 脚本',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      table_label: '出问题的表',
      table_ph: '如 dws.orders_daily',
      column_label: '出问题的列（可选）',
      column_ph: '如 gmv',
      symptom_label: '症状（可选）',
      symptom_ph: '如 gmv 自 10-05 起翻倍',
      run_btn: '追踪',
      clear_btn: '清空',
      empty_input: '请先粘贴 SQL 并填出问题的表。',
      report_ph: '▶ 嫌疑排行与验证 SQL 在此显示。',
      llm_label: 'LLM 追踪通报（需 API key）',
      home: '首页',
      running: '追踪中…',
    },
  },
}

export default initI18n(resources)
