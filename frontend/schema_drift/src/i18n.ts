import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/schema_drift/ui.py). The legacy `title` markdown is split
// into title (heading, 🧬 glyph moves next to the h1) + subtitle.
// Report wording stays in Python (report.py) and arrives localized.
const resources = {
  en: {
    translation: {
      title: 'Schema Drift Check',
      subtitle:
        'Compare two schema snapshots (CREATE TABLE scripts) and ' +
        'report every structural change with a severity level — ' +
        'breaking / risk / info. Sibling of /impact: that page ' +
        'covers SQL logic changes, this one covers table ' +
        'structure. No database connection.',
      dialect_label: 'SQL dialect',
      old_label: 'Old DDL',
      old_ph: 'Paste the old CREATE TABLE script…',
      new_label: 'New DDL',
      new_ph: 'Paste the new CREATE TABLE script…',
      diff_btn: 'Compare',
      dirs_acc: 'Compare two directories',
      old_dir_label: 'Old directory / file',
      new_dir_label: 'New directory / file',
      dirs_btn: 'Compare directories',
      empty_sql: '⚠️ Paste both DDL scripts first.',
      empty_dirs: '⚠️ Provide both paths first.',
      bad_path: '⚠️ Path does not exist: ',
      running: 'Comparing…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: 'Schema 漂移检查',
      subtitle:
        '对比两份 Schema 快照（CREATE TABLE 脚本），按严重度分级' +
        '报告每一处结构变更 — 破坏 / 风险 / 提示。与变更影响分析' +
        '(/impact) 互补：那里管 SQL 逻辑变更，这里管表结构变更。' +
        '不连接数据库。',
      dialect_label: 'SQL 方言',
      old_label: '旧版 DDL',
      old_ph: '粘贴旧版 CREATE TABLE 脚本…',
      new_label: '新版 DDL',
      new_ph: '粘贴新版 CREATE TABLE 脚本…',
      diff_btn: '对比',
      dirs_acc: '对比两个目录',
      old_dir_label: '旧目录 / 文件',
      new_dir_label: '新目录 / 文件',
      dirs_btn: '对比目录',
      empty_sql: '⚠️ 请先粘贴两份 DDL。',
      empty_dirs: '⚠️ 请先填写两个路径。',
      bad_path: '⚠️ 路径不存在: ',
      running: '对比中…',
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
