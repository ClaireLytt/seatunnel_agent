import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Warehouse Hygiene',
      subtitle:
        'Lineage-driven dead-weight report — write-only tables, columns ' +
        'nothing ever selects, and DDL definitions no lineage touches. ' +
        'No database connection, nothing executed.',
      dir_label: 'SQL directory',
      dir_ph:
        'Directory containing *.sql files (scanned recursively), ' +
        'e.g. examples/pii_demo',
      dialect_label: 'SQL dialect',
      scan_btn: 'Analyze directory',
      inline_acc: 'Analyze pasted SQL',
      sql_label: 'SQL input',
      sql_ph: 'Paste CREATE TABLE / INSERT ... SELECT statements…',
      scan_sql_btn: 'Analyze SQL',
      empty_dir: '⚠️ Provide a SQL directory first.',
      bad_dir: '⚠️ Not a directory: ',
      empty_sql: '⚠️ Paste some SQL first.',
      running: 'Analyzing…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '数仓卫生检查',
      subtitle:
        '血缘驱动的死重报告 — 只写不读的表、无人取的列、不在任何血缘里的 ' +
        'DDL 定义。不连接数据库、不执行任何语句。',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/pii_demo',
      dialect_label: 'SQL 方言',
      scan_btn: '分析目录',
      inline_acc: '分析粘贴的 SQL',
      sql_label: 'SQL 输入',
      sql_ph: '粘贴 CREATE TABLE / INSERT ... SELECT 语句…',
      scan_sql_btn: '分析 SQL',
      empty_dir: '⚠️ 请先填写 SQL 目录。',
      bad_dir: '⚠️ 不是有效目录: ',
      empty_sql: '⚠️ 请先粘贴 SQL。',
      running: '分析中…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
