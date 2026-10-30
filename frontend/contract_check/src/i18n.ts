import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Data Contract',
      subtitle:
        'Check actual DDL against the promises a team declared in YAML — ' +
        'missing tables and columns, type and partition violations, ' +
        'comment requirements. No database connection, nothing executed.',
      extra_label: 'Contract (YAML)',
      extra_ph:
        'tables:\n' +
        '  - name: dwd.orders\n' +
        '    columns:\n' +
        '      - { name: order_id, type: bigint }\n' +
        '      - { name: amount, type: decimal, comment: true }\n' +
        '    partitioned_by: [dt]',
      dir_label: 'SQL directory',
      dir_ph:
        'Directory containing *.sql files (scanned recursively), ' +
        'e.g. examples/pii_demo',
      dialect_label: 'SQL dialect',
      scan_btn: 'Check directory',
      inline_acc: 'Check pasted DDL',
      sql_label: 'DDL input',
      sql_ph: 'Paste CREATE TABLE statements…',
      scan_sql_btn: 'Check DDL',
      empty_dir: '⚠️ Provide a SQL directory first.',
      empty_extra: '⚠️ Paste the YAML contract first.',
      bad_dir: '⚠️ Not a directory: ',
      empty_sql: '⚠️ Paste some DDL first.',
      running: 'Checking…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '数据契约校验',
      subtitle:
        '拿 YAML 里声明的表承诺对照实际 DDL — 表/列缺失、类型与分区' +
        '违约、注释要求逐条报出。不连接数据库、不执行任何语句。',
      extra_label: '契约（YAML）',
      extra_ph:
        'tables:\n' +
        '  - name: dwd.orders\n' +
        '    columns:\n' +
        '      - { name: order_id, type: bigint }\n' +
        '      - { name: amount, type: decimal, comment: true }\n' +
        '    partitioned_by: [dt]',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/pii_demo',
      dialect_label: 'SQL 方言',
      scan_btn: '校验目录',
      inline_acc: '校验粘贴的 DDL',
      sql_label: 'DDL 输入',
      sql_ph: '粘贴 CREATE TABLE 语句…',
      empty_dir: '⚠️ 请先填写 SQL 目录。',
      empty_extra: '⚠️ 请先粘贴契约 YAML。',
      bad_dir: '⚠️ 不是有效目录: ',
      empty_sql: '⚠️ 请先粘贴 DDL。',
      scan_sql_btn: '校验 DDL',
      running: '校验中…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
