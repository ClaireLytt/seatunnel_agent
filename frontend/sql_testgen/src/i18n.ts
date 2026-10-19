import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/sql_testgen/ui.py). The legacy `title` markdown is split
// into title (heading) + subtitle (body); backend-rendered report keys
// stay in Python (report.py).
const resources = {
  en: {
    translation: {
      title: 'SQL Test Data Generator',
      subtitle:
        'Generate minimal per-table datasets that actually exercise ' +
        'a query: equi-join columns share value pools, WHERE ' +
        'literals are satisfied, boundary rows (NULL/zero/empty) ' +
        'are mixed in — then optionally execute everything on ' +
        'in-memory SQLite. No external database.',
      sql_label: 'Query SQL',
      sql_ph: 'Paste the SELECT / INSERT...SELECT to generate data for…',
      ddl_label: 'DDL (optional)',
      ddl_ph: 'CREATE TABLE statements for exact column types…',
      dialect_label: 'SQL dialect',
      rows_label: 'Rows per table',
      validate_label: 'Validate on SQLite',
      gen_btn: 'Generate',
      empty_sql: '⚠️ Paste a query first.',
      home: 'Home',
      running: 'Generating…',
    },
  },
  zh: {
    translation: {
      title: 'SQL 测试数据生成',
      subtitle:
        '为查询生成最小可用的测试数据集：关联列共享取值池、WHERE ' +
        '字面量被满足、混入边界行（NULL/零值/空串）——并可选在内存 ' +
        'SQLite 上执行整条链路验证。不依赖外部数据库。',
      sql_label: '查询 SQL',
      sql_ph: '粘贴需要造数的 SELECT / INSERT...SELECT…',
      ddl_label: 'DDL（可选）',
      ddl_ph: '粘贴 CREATE TABLE 以获得精确的列类型…',
      dialect_label: 'SQL 方言',
      rows_label: '每表行数',
      validate_label: 'SQLite 验证',
      gen_btn: '生成测试数据',
      empty_sql: '⚠️ 请先粘贴查询 SQL。',
      home: '首页',
      running: '生成中…',
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
