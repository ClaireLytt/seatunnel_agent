import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { langFromCookie } from '@shared/lang'

const resources = {
  en: {
    translation: {
      title: 'Text2SQL · Chat BI',
      subtitle: 'Ask in natural language — schema matched, SQL generated and run.',
      dsType: 'Datasource',
      host: 'Host',
      port: 'Port',
      database: 'Database',
      username: 'Username',
      password: 'Password',
      connect: 'Connect',
      connecting: 'Connecting…',
      connected: 'Connected · {{count}} tables',
      connectFailed: 'Connect failed: {{msg}}',
      notConnected: 'Not connected',
      home: 'Home',
      legacy: 'Legacy page',
      askPh: 'Ask about your data…',
      send: 'Send',
      stop: 'Stop',
      newChat: 'New chat',
    },
  },
  zh: {
    translation: {
      title: 'Text2SQL · Chat BI · 智能问数',
      subtitle: '自然语言提问 — 自动匹配表结构,生成并执行 SQL。',
      dsType: '数据源',
      host: '主机',
      port: '端口',
      database: '数据库',
      username: '用户名',
      password: '密码',
      connect: '连接',
      connecting: '连接中…',
      connected: '已连接 · {{count}} 张表',
      connectFailed: '连接失败: {{msg}}',
      notConnected: '未连接',
      home: '首页',
      legacy: '旧版页面',
      askPh: '问点数据相关的…',
      send: '发送',
      stop: '停止',
      newChat: '新会话',
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
