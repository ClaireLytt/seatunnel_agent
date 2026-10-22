import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/sql_transpile/ui.py). The legacy `title` markdown is split
// into title (heading) + subtitle (body); backend-rendered report keys stay
// in Python (i18n.py / report.py).
const resources = {
  en: {
    translation: {
      title: 'SQL Dialect Translation',
      subtitle:
        'hive / spark / doris / starrocks — deterministic sqlglot ' +
        'translation with a structured incompatibility report. ' +
        'No database connection, the SQL is never executed.',
      src_label: 'Source dialect',
      src_auto: 'Auto detect',
      dst_label: 'Target dialect',
      sql_label: 'SQL input',
      sql_ph: 'Paste one or more ;-separated statements…',
      translate_btn: 'Translate',
      batch_acc: 'Batch translate a directory',
      dir_label: 'SQL directory',
      dir_ph: 'Directory containing *.sql files (scanned recursively)',
      out_label: 'Output directory (optional)',
      out_ph: 'Translated files mirror the input tree when set',
      batch_btn: 'Batch translate',
      result_label: 'Translated SQL',
      empty_sql: '⚠️ Paste some SQL first.',
      empty_dir: '⚠️ Provide a SQL directory first.',
      bad_dir: '⚠️ Not a directory: ',
      advice_acc: 'LLM advice (optional, llm-generated)',
      advice_btn: 'Generate LLM advice',
      advice_none: 'No findings that need LLM advice.',
      advice_no_key:
        'No API key configured — deterministic results above are unaffected.',
      home: 'Home',
      copy: 'Copy',
      copied: 'Copied',
      running: 'Translating…',
      advising: 'Generating…',
    },
  },
  zh: {
    translation: {
      title: 'SQL 方言翻译',
      subtitle:
        'hive / spark / doris / starrocks 互转 — 基于 sqlglot 的确定性' +
        '翻译 + 结构化不兼容点清单。不连接数据库，不执行 SQL。',
      src_label: '源方言',
      src_auto: '自动推断',
      dst_label: '目标方言',
      sql_label: 'SQL 输入',
      sql_ph: '粘贴一条或多条以 ; 分隔的 SQL…',
      translate_btn: '翻译',
      batch_acc: '批量翻译目录',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描）',
      out_label: '输出目录（可选）',
      out_ph: '填写后按原目录结构写出翻译文件',
      batch_btn: '批量翻译',
      result_label: '翻译后 SQL',
      empty_sql: '⚠️ 请先粘贴 SQL。',
      empty_dir: '⚠️ 请先填写 SQL 目录。',
      bad_dir: '⚠️ 不是有效目录: ',
      advice_acc: 'LLM 建议（可选，llm-generated）',
      advice_btn: '生成 LLM 建议',
      advice_none: '没有需要 LLM 建议的不兼容点。',
      advice_no_key: '未配置 API key — 上方确定性结果不受影响。',
      home: '首页',
      copy: '复制',
      copied: '已复制',
      running: '翻译中…',
      advising: '生成中…',
    },
  },
}

export default initI18n(resources)
