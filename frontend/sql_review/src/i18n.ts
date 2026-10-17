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
      ddlAccordion: 'Table DDL (optional, for schema checks)',
      ddlLabel: 'CREATE TABLE statements',
      rulesAccordion: 'Rule config (optional, .sqlreview.yaml format)',
      rulesLabel: 'YAML rules',
      rulesPlaceholder: 'partition_columns: [dt, ds]\nthresholds:\n  max_joins: 5',
      rulesInvalid: '❌ Invalid rule config',
      downloadReport: 'Download Report (.md)',
      reviewBtn: 'Start Review',
      reviewing: 'Reviewing…',
      fixBtn: 'Generate Fixed SQL (LLM)',
      clearBtn: 'Clear',
      reportPlaceholder: 'The review report will appear here',
      fixedSql: 'Fixed SQL',
      inputSqlFirst: 'Please enter SQL first.',
      reviewFailed: '❌ Review failed',
      fixNeedReview: '-- Run a review first',
      fixGenerating: '-- Calling the LLM to generate fixed SQL, please wait…',
      fixFailed: '-- Fix failed',
      fixNoneStatic:
        '-- No mechanically fixable issue found; switch to LLM review mode for a full rewrite',
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
      ddlAccordion: '表结构 DDL（可选，用于 schema 校验）',
      ddlLabel: 'CREATE TABLE 语句',
      rulesAccordion: '规则配置（可选，.sqlreview.yaml 格式）',
      rulesLabel: 'YAML 规则',
      rulesPlaceholder: 'partition_columns: [dt, ds]\nthresholds:\n  max_joins: 5',
      rulesInvalid: '❌ 规则配置无效',
      downloadReport: '下载报告（.md）',
      reviewBtn: '开始审查',
      reviewing: '审查中…',
      fixBtn: '生成修复 SQL（LLM）',
      clearBtn: '清空',
      reportPlaceholder: '审查报告将显示在这里',
      fixedSql: '修复后 SQL',
      inputSqlFirst: '请先输入 SQL。',
      reviewFailed: '❌ 审查失败',
      fixNeedReview: '-- 请先完成一次审查',
      fixGenerating: '-- 正在调用 LLM 生成修复 SQL，请稍候……',
      fixFailed: '-- 修复失败',
      fixNoneStatic: '-- 没有可静态自动修复的问题；如需完整改写请切换到 LLM 审查模式',
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
