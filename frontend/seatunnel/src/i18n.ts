import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

const resources = {
  en: {
    translation: {
      title: 'SeaTunnel Pipeline Builder',
      subtitle: 'AI Agent · ReAct Pattern · Auto-diagnose & Fix',
      sessions: 'Sessions',
      noSessions: 'No sessions yet',
      chatEmpty: 'Describe the pipeline you want to build',
      inputPlaceholder: 'Message SeaTunnel Agent...',
      mode: 'Mode',
      templates: 'Templates',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: 'SeaTunnel Pipeline Builder',
      subtitle: 'AI Agent · ReAct 模式 · 自动诊断修复',
      sessions: '会话',
      noSessions: '暂无会话',
      chatEmpty: '描述你想构建的数据管道',
      inputPlaceholder: '给 SeaTunnel Agent 发送消息…',
      mode: '模式',
      templates: '配置模板',
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
