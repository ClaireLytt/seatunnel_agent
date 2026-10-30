import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Grant Surface',
      subtitle:
        'Parse GRANT/REVOKE statements, net them, and grade the surviving ' +
        'surface — grants to PUBLIC, ALL PRIVILEGES, database-wide scopes, ' +
        'and grants on tables the PII scanner flags in the same script. ' +
        'No database connection, nothing executed.',
      dir_label: 'SQL directory',
      dir_ph: 'Directory containing *.sql files (scanned recursively), ' + 'e.g. examples/pii_demo',
      dialect_label: 'SQL dialect',
      scan_btn: 'Scan directory',
      inline_acc: 'Scan pasted SQL',
      sql_label: 'SQL input',
      sql_ph: 'Paste GRANT statements (with the DDL for PII linkage)…',
      scan_sql_btn: 'Scan SQL',
      empty_sql: 'Paste some SQL first.',
      running: 'Scanning…',
    },
  },
  zh: {
    translation: {
      title: '权限面扫描',
      subtitle:
        '解析 GRANT/REVOKE 并做净面 — 分级报出对 PUBLIC 的授权、' +
        'ALL 宽权限、库级宽范围,以及对同脚本 PII 命中表的授权。' +
        '不连接数据库、不执行任何语句。',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/pii_demo',
      dialect_label: 'SQL 方言',
      scan_btn: '扫描目录',
      inline_acc: '扫描粘贴的 SQL',
      sql_label: 'SQL 输入',
      sql_ph: '粘贴 GRANT 语句（同时粘 DDL 可联动 PII 命中）…',
      empty_sql: '请先粘贴 SQL。',
      scan_sql_btn: '扫描 SQL',
      running: '扫描中…',
    },
  },
}

export default initI18n(resources)
