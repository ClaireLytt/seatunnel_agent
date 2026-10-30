import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Metadata Quality',
      subtitle:
        'DDL-level conventions check — comment coverage, cross-layer ' +
        'naming mismatches, and type anti-patterns (money on FLOAT, ' +
        'dates as bare STRING). No database connection, nothing executed.',
      dir_label: 'SQL directory',
      dir_ph: 'Directory containing *.sql files (scanned recursively), ' + 'e.g. examples/pii_demo',
      dialect_label: 'SQL dialect',
      scan_btn: 'Check directory',
      inline_acc: 'Check pasted DDL',
      sql_label: 'DDL input',
      sql_ph: 'Paste CREATE TABLE statements…',
      scan_sql_btn: 'Check DDL',
      empty_sql: 'Paste some DDL first.',
      running: 'Checking…',
    },
  },
  zh: {
    translation: {
      title: '元数据质量体检',
      subtitle:
        'DDL 层规约检查 — 注释覆盖率、跨层命名错配、类型反模式' +
        '（金额用浮点、日期用裸 STRING）。不连接数据库、不执行任何语句。',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/pii_demo',
      dialect_label: 'SQL 方言',
      scan_btn: '检查目录',
      inline_acc: '检查粘贴的 DDL',
      sql_label: 'DDL 输入',
      sql_ph: '粘贴 CREATE TABLE 语句…',
      empty_sql: '请先粘贴 DDL。',
      scan_sql_btn: '检查 DDL',
      running: '检查中…',
    },
  },
}

export default initI18n(resources)
