import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/sql_fmt/ui.py). The legacy `title` markdown is split
// into title (heading) + subtitle (body); backend-rendered report keys stay
// in Python (report.py).
const resources = {
  en: {
    translation: {
      title: 'SQL Formatter',
      subtitle:
        'Deterministic sqlglot pretty-print with a black-style ' +
        'workflow — format pasted SQL, or check a directory for ' +
        'files that would be reformatted. Statements that do not ' +
        'parse are kept verbatim; the UI never writes files ' +
        "(use the CLI's --write).",
      sql_label: 'SQL input',
      sql_ph: 'Paste one or more ;-separated statements…',
      dialect_label: 'SQL dialect',
      fmt_btn: 'Format',
      dir_acc: 'Check a directory',
      dir_label: 'SQL directory',
      dir_ph: 'Directory containing *.sql (scanned recursively), ' + 'e.g. examples/sqlfmt_demo',
      dir_btn: 'Check directory',
      empty_sql: 'Paste some SQL first.',
      empty_dir: 'Provide a SQL directory first.',
      bad_dir: 'Not a directory: ',
      home: 'Home',
      running: 'Formatting…',
    },
  },
  zh: {
    translation: {
      title: 'SQL 格式化',
      subtitle:
        '基于 sqlglot 的确定性格式化，black 式工作流 — 粘贴 SQL ' +
        '直接格式化，或检查目录里哪些文件需要重排。解析失败的语句' +
        '原样保留；页面只做检查不写文件（写回用 CLI 的 --write）。',
      sql_label: 'SQL 输入',
      sql_ph: '粘贴一条或多条以 ; 分隔的 SQL…',
      dialect_label: 'SQL 方言',
      fmt_btn: '格式化',
      dir_acc: '检查目录',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/sqlfmt_demo',
      dir_btn: '检查目录',
      empty_sql: '请先粘贴 SQL。',
      empty_dir: '请先填写 SQL 目录。',
      bad_dir: '不是有效目录: ',
      home: '首页',
      running: '格式化中…',
    },
  },
}

export default initI18n(resources)
