import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Field Usage',
      subtitle:
        'Before a table is offboarded or a column trimmed, someone asks ' +
        '"does anyone still read it?". Paste the DDL and a query ' +
        'workload — every column gets its reference count, never-read ' +
        'tables and columns are called out, SELECT * blind spots ' +
        'flagged.',
      ddl_label: 'CREATE TABLE DDL',
      ddl_ph: 'CREATE TABLE dwd.orders ( ... );',
      queries_label: 'Query workload (a batch of SQL)',
      queries_ph: 'SELECT o.amount FROM dwd.orders o ...;',
      run_btn: 'Analyze usage',
      clear_btn: 'Clear',
      empty_input: 'Paste the DDL and the query workload first.',
      report_ph: '▶ Per-column reference counts appear here.',
      llm_label: 'LLM disposition advice (needs an API key)',
      home: 'Home',
      running: 'Analyzing…',
    },
  },
  zh: {
    translation: {
      title: '字段使用率',
      subtitle:
        '下线一张表、裁剪一个列之前，总得先回答"还有人读吗"。粘贴 DDL ' +
        '和一批查询 SQL — 逐列给出引用计数，没人读的表与列点名，' +
        'SELECT * 盲区标出。',
      ddl_label: 'CREATE TABLE DDL',
      ddl_ph: 'CREATE TABLE dwd.orders ( ... );',
      queries_label: '查询负载（一批 SQL）',
      queries_ph: 'SELECT o.amount FROM dwd.orders o ...;',
      run_btn: '开始盘点',
      clear_btn: '清空',
      empty_input: '请先粘贴 DDL 与查询负载。',
      report_ph: '▶ 逐列引用计数在此显示。',
      llm_label: 'LLM 处置建议（需 API key）',
      home: '首页',
      running: '盘点中…',
    },
  },
}

export default initI18n(resources)
