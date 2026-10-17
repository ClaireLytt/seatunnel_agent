import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

// Strings ported verbatim from the legacy Python dictionary
// (agents/data/sql_review/i18n.py); markdown heading markers dropped —
// the React page renders real headings.
const resources = {
  en: {
    translation: {
      title: '🔍 SQL Code Review',
      subtitle:
        'Static rules + LLM semantic review. Supports Hive / Spark / Flink / ' +
        'MaxCompute / MySQL / PostgreSQL / SQL Server / ClickHouse / Doris / ' +
        'SQLite. Pure static analysis — the SQL is never executed.',
      sqlPlaceholder: 'Paste the SQL to review…',
      dialect: 'SQL Dialect',
      mode: 'Review Mode',
      modeStatic: 'Static review (fast, no LLM)',
      modeLlm: 'LLM deep review',
      reviewBtn: 'Start Review',
      reviewing: 'Reviewing…',
      reportPlaceholder: 'The review report will appear here',
      inputSqlFirst: 'Please enter SQL first.',
      reviewFailed: '❌ Review failed',
      home: 'Home',
      report: 'Report',
    },
  },
  zh: {
    translation: {
      title: '🔍 SQL 代码审查',
      subtitle:
        '静态规则 + LLM 语义审查，支持 Hive / Spark / Flink / MaxCompute / ' +
        'MySQL / PostgreSQL / SQL Server / ClickHouse / Doris / SQLite。' +
        '纯静态分析，不执行 SQL。',
      sqlPlaceholder: '粘贴要审查的 SQL……',
      dialect: 'SQL 方言',
      mode: '审查模式',
      modeStatic: '静态审查（快速，无需 LLM）',
      modeLlm: 'LLM 深度审查',
      reviewBtn: '开始审查',
      reviewing: '审查中…',
      reportPlaceholder: '审查报告将显示在这里',
      inputSqlFirst: '请先输入 SQL。',
      reviewFailed: '❌ 审查失败',
      home: '首页',
      report: '报告',
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
