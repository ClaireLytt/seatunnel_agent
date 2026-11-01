import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Avro to DDL',
      subtitle:
        'The topic has a schema; the landing table gets typed by hand ' +
        'and drifts from day one. Paste the Avro record or JSON Schema ' +
        '— logical types map to DECIMAL/DATE/TIMESTAMP, nullable unions ' +
        'unwrap, lossy rows are named, and the CREATE TABLE parses ' +
        'clean.',
      schema_label: 'Avro record or JSON Schema',
      schema_ph: '{"type": "record", "name": "Order", "fields": [ ... ]}',
      table_label: 'Table name (optional)',
      table_ph: 'e.g. ods.orders_raw',
      dialect_label: 'Dialect (hive / doris)',
      run_btn: 'Generate DDL',
      clear_btn: 'Clear',
      empty_input: 'Paste the schema first.',
      report_ph: '▶ The column mapping and CREATE TABLE appear here.',
      llm_label: 'LLM landing review (needs an API key)',
      home: 'Home',
      running: 'Converting…',
    },
  },
  zh: {
    translation: {
      title: '消息 Schema 建表',
      subtitle:
        'topic 有 Schema，落地表却靠手敲，第一天就开始漂。粘贴 Avro ' +
        'record 或 JSON Schema — logicalType 对号映射 DECIMAL/DATE/' +
        'TIMESTAMP，可空 union 解包，有损行点名，建表语句解析零错误。',
      schema_label: 'Avro record 或 JSON Schema',
      schema_ph: '{"type": "record", "name": "Order", "fields": [ ... ]}',
      table_label: '表名（可选）',
      table_ph: '如 ods.orders_raw',
      dialect_label: '方言（hive / doris）',
      run_btn: '生成建表语句',
      clear_btn: '清空',
      empty_input: '请先粘贴 Schema。',
      report_ph: '▶ 列映射与 CREATE TABLE 在此显示。',
      llm_label: 'LLM 落地评审（需 API key）',
      home: '首页',
      running: '转换中…',
    },
  },
}

export default initI18n(resources)
