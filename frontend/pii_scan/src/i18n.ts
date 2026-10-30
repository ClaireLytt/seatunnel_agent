import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/pii_scan/ui.py). The legacy `title` markdown is split into
// title (heading, 🔒 glyph moves next to the h1) + subtitle. The legacy
// `result_label` key was defined but unused in the layout — dropped.
// Report wording stays in Python (report.py) and arrives localized.
const resources = {
  en: {
    translation: {
      title: 'PII / Sensitive Column Scan',
      subtitle:
        'Naming rules × column lineage — find sensitive columns in ' +
        'SQL files and trace where they spread downstream, flagging ' +
        'unmasked propagation. No database connection, nothing ' +
        'executed.',
      dir_label: 'SQL directory',
      dir_ph: 'Directory containing *.sql files (scanned recursively), ' + 'e.g. examples/pii_demo',
      dialect_label: 'SQL dialect',
      scan_btn: 'Scan directory',
      inline_acc: 'Scan pasted SQL',
      sql_label: 'SQL input',
      sql_ph: 'Paste CREATE TABLE / INSERT ... SELECT statements…',
      scan_sql_btn: 'Scan SQL',
      empty_dir: 'Provide a SQL directory first.',
      bad_dir: 'Not a directory: ',
      empty_sql: 'Paste some SQL first.',
      running: 'Scanning…',
      home: 'Home',
      mask_btn: 'Generate masking SQL',
      mask_conf_label: 'Mask weak hits (e.g. bare `name`) too',
      mask_result_label: 'Masking plan — review before running',
      mask_copy: 'Copy SQL',
      mask_copied: 'Copied',
    },
  },
  zh: {
    translation: {
      title: '敏感数据扫描 (PII)',
      subtitle:
        '命名规则 × 字段血缘 — 在 SQL 文件中识别敏感列，并沿血缘追踪' +
        '下游扩散，标出未脱敏的传播路径。不连接数据库、不执行任何语句。',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/pii_demo',
      dialect_label: 'SQL 方言',
      scan_btn: '扫描目录',
      inline_acc: '扫描粘贴的 SQL',
      sql_label: 'SQL 输入',
      sql_ph: '粘贴 CREATE TABLE / INSERT ... SELECT 语句…',
      scan_sql_btn: '扫描 SQL',
      empty_dir: '请先填写 SQL 目录。',
      bad_dir: '不是有效目录: ',
      empty_sql: '请先粘贴 SQL。',
      running: '扫描中…',
      home: '首页',
      mask_btn: '生成脱敏 SQL',
      mask_conf_label: '弱命中（如裸 name 列）也脱敏',
      mask_result_label: '脱敏方案 — 执行前请人工复核',
      mask_copy: '复制 SQL',
      mask_copied: '已复制',
    },
  },
}

export default initI18n(resources)
