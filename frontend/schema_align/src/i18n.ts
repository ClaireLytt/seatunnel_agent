import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Schema Align',
      subtitle:
        'Will the sync job survive real data? Paste the source and sink ' +
        'CREATE TABLE DDLs — columns match by name and every mapping is ' +
        'judged: dropped columns, NOT NULL traps, type narrowings, ' +
        'risky string conversions and temporal truncation, each with a ' +
        'prescription. Widenings pass silently. No database connection.',
      source_label: 'Source table DDL',
      sink_label: 'Sink table DDL',
      ddl_ph: 'CREATE TABLE orders (order_id BIGINT NOT NULL, ...)',
      run_btn: 'Align',
      clear_btn: 'Clear',
      empty_input: 'Paste both DDLs first.',
      report_ph: '▶ Graded mapping risks appear here.',
      llm_label: 'LLM alignment review (needs an API key)',
      home: 'Home',
      running: 'Aligning…',
    },
  },
  zh: {
    translation: {
      title: '源目对齐体检',
      subtitle:
        '同步作业遇到真实数据还活得下来吗？粘贴源表与目标表两份建表 ' +
        'DDL — 按列名匹配后逐列判定：丢列、NOT NULL 陷阱、类型收窄、' +
        '危险字符串转换与时间截断，每条附处方。放宽类转换静默通过。' +
        '不连数据库。',
      source_label: '源表 DDL',
      sink_label: '目标表 DDL',
      ddl_ph: 'CREATE TABLE orders (order_id BIGINT NOT NULL, ...)',
      run_btn: '体检',
      clear_btn: '清空',
      empty_input: '请先粘贴两份 DDL。',
      report_ph: '▶ 分级映射风险在此显示。',
      llm_label: 'LLM 对齐评审（需 API key）',
      home: '首页',
      running: '体检中…',
    },
  },
}

export default initI18n(resources)
