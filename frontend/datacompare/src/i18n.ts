import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

// Only the keys this skeleton needs; the full legacy dictionary
// (~247 keys) is ported in ticket 10.
const resources = {
  en: {
    translation: {
      title: 'Data Comparison',
      subtitle: 'Compare schemas, row counts, and data across two data sources.',
      sourceA: 'Source A',
      sourceB: 'Source B',
      dsType: 'Datasource',
      host: 'Host',
      port: 'Port',
      database: 'Database',
      username: 'Username',
      password: 'Password',
      connect: 'Connect',
      connecting: 'Connecting…',
      selectTable: 'Select Table',
      results: 'Results',
      resultsEmpty: 'Connect both sources and pick tables to start comparing.',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '数据比对',
      subtitle: '跨数据源比对表结构、行数、数据差异。',
      sourceA: '数据源 A',
      sourceB: '数据源 B',
      dsType: '数据源类型',
      host: '主机地址',
      port: '端口',
      database: '数据库',
      username: '用户名',
      password: '密码',
      connect: '连接',
      connecting: '连接中…',
      selectTable: '选择表',
      results: '结果区',
      resultsEmpty: '连接两侧数据源并选择表后开始比对。',
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
