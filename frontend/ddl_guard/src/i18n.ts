import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Migration Guard',
      subtitle:
        'Grade the dangerous operations in a DDL migration script — drops, ' +
        'truncates, type narrowing, renames — and generate the rollback ' +
        'script, irreversible steps explicitly marked. No database ' +
        'connection, nothing executed.',
      dir_label: 'SQL directory',
      dir_ph:
        'Directory containing *.sql files (scanned recursively), ' +
        'e.g. examples/pii_demo',
      dialect_label: 'SQL dialect',
      scan_btn: 'Guard directory',
      inline_acc: 'Guard pasted migration',
      sql_label: 'Migration SQL',
      sql_ph: 'Paste ALTER/DROP statements (include the CREATE TABLE for a fuller rollback)…',
      scan_sql_btn: 'Guard SQL',
      empty_dir: '⚠️ Provide a SQL directory first.',
      bad_dir: '⚠️ Not a directory: ',
      empty_sql: '⚠️ Paste some migration SQL first.',
      running: 'Scanning…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '迁移守卫',
      subtitle:
        '对上线迁移脚本的危险操作分级 — 删表/清空/类型收窄/重命名 — ' +
        '并生成回滚脚本,不可逆步骤显式标注。不连接数据库、不执行任何语句。',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/pii_demo',
      dialect_label: 'SQL 方言',
      scan_btn: '守卫目录',
      inline_acc: '守卫粘贴的迁移脚本',
      sql_label: '迁移 SQL',
      sql_ph: '粘贴 ALTER/DROP 语句（附上 CREATE TABLE 可生成更完整的回滚）…',
      empty_dir: '⚠️ 请先填写 SQL 目录。',
      bad_dir: '⚠️ 不是有效目录: ',
      empty_sql: '⚠️ 请先粘贴迁移 SQL。',
      scan_sql_btn: '守卫 SQL',
      running: '扫描中…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
