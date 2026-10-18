import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

// UI-chrome keys ported verbatim from the backend dsk() dict
// (agents/data/data_skew/i18n.py). The legacy `dsk_title` markdown is
// split into title (heading, ⚖️ glyph moves next to the h1) + the
// existing dsk_subtitle. Guard/validation and report wording stays in
// Python i18n.py and reaches the page already localized (structured
// {code, message} errors / report markdown).
const resources = {
  en: {
    translation: {
      title: 'SQL Data Skew Analyzer',
      subtitle:
        'Static skew-pattern rules + LLM rewrite. Supports Spark SQL ' +
        '(Spark 3) and MaxCompute SQL (Hive accepted as compatible ' +
        'input). Static analysis by default — optionally connect a data ' +
        'source to verify skew with real key distributions.',
      sql_label: 'SQL',
      sql_ph: 'Paste the SQL to analyze for data skew…',
      dialect: 'SQL Dialect',
      mode: 'Analysis Mode',
      mode_static: 'Static scan (fast, no LLM)',
      mode_llm: 'LLM optimize (rewrite SQL)',
      analyze_btn: 'Analyze Skew',
      upload_btn: 'Upload SQL file',
      clear_btn: 'Clear',
      running_static: 'Running static skew scan…',
      running_llm: 'LLM is analyzing and rewriting the SQL…',
      report_placeholder: 'The skew analysis report will appear here',
      download_report: 'Download Report (.md)',
      download_sql: 'Download Optimized SQL (.sql)',
      optimized_sql: 'Optimized SQL',
      history_accordion: 'Analysis history (last 20)',
      history_refresh: 'Refresh',
      history_load: 'Load selected',
      history_pick: 'Pick a record',
      history_empty: 'No history yet — run an analysis first.',
      h_time: 'Time',
      h_source: 'Source',
      h_dialect: 'Dialect',
      h_mode: 'Mode',
      h_findings: 'Findings',
      h_sql: 'SQL',
      home: 'Home',
      copy: 'Copy',
      copied: 'Copied',
    },
  },
  zh: {
    translation: {
      title: 'SQL 数据倾斜分析',
      subtitle:
        '静态倾斜规则 + LLM 改写。支持 Spark SQL（Spark 3）与 MaxCompute ' +
        'SQL（Hive 作为兼容输入）。默认纯静态分析不执行 SQL；可选连接' +
        '数据源，用真实键值分布验证倾斜。',
      sql_label: 'SQL',
      sql_ph: '粘贴需要分析数据倾斜的 SQL 脚本…',
      dialect: 'SQL 方言',
      mode: '分析模式',
      mode_static: '静态扫描（快速，不调用 LLM）',
      mode_llm: 'LLM 优化（改写 SQL）',
      analyze_btn: '开始分析',
      upload_btn: '上传 SQL 文件',
      clear_btn: '清空',
      running_static: '正在执行静态倾斜扫描…',
      running_llm: 'LLM 正在分析并改写 SQL…',
      report_placeholder: '倾斜分析报告将显示在这里',
      download_report: '下载报告（.md）',
      download_sql: '下载优化后 SQL（.sql）',
      optimized_sql: '优化后 SQL',
      history_accordion: '分析历史（最近 20 条）',
      history_refresh: '刷新',
      history_load: '载入所选',
      history_pick: '选择记录',
      history_empty: '暂无历史记录——先执行一次分析。',
      h_time: '时间',
      h_source: '来源',
      h_dialect: '方言',
      h_mode: '模式',
      h_findings: '发现',
      h_sql: 'SQL',
      home: '首页',
      copy: '复制',
      copied: '已复制',
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
