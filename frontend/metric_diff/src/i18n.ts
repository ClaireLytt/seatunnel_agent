import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/metric_diff/ui.py). The legacy `title` markdown is split
// into title (heading, 📏 glyph moves next to the h1) + subtitle.
// Report wording stays in Python (i18n.py/report.py) and arrives localized.
const resources = {
  en: {
    translation: {
      title: 'Metric Consistency Check',
      subtitle:
        'Find same-named output columns DEFINED differently across ' +
        'jobs — the number-one reason two reports disagree. ' +
        'Expressions are canonicalized before comparing, so ' +
        'formatting differences never flag. No database, no LLM.',
      dir_label: 'SQL directory',
      dir_ph:
        'Directory containing *.sql (scanned recursively), ' +
        'e.g. examples/metricdiff_demo',
      dialect_label: 'SQL dialect',
      check_btn: 'Check metrics',
      empty_dir: '⚠️ Provide a SQL directory first.',
      bad_dir: '⚠️ Not a directory: ',
      running: 'Checking…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '指标口径一致性检查',
      subtitle:
        '找出不同作业里同名但定义不同的输出列 — 「两张报表数对' +
        '不上」的头号原因。表达式先归一化再比较，排版差异不会误报。' +
        '不连数据库、不调用 LLM。',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/metricdiff_demo',
      dialect_label: 'SQL 方言',
      check_btn: '检查口径',
      empty_dir: '⚠️ 请先填写 SQL 目录。',
      bad_dir: '⚠️ 不是有效目录: ',
      running: '检查中…',
      home: '首页',
    },
  },
}

i18n.use(initReactI18next).init({
  resources,
  lng: langFromCookie(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
