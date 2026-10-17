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
      send: 'Send',
      stop: 'Stop',
      mode: 'MODE',
      templates: 'TEMPLATES',
      home: 'Home',
      configPath: 'CONFIG / LOG PATH',
      connect: 'Connect',
      connecting: 'Connecting...',
      status: 'STATUS',
      statusDefault: 'Not connected',
      tplNone: '-- Select a template --',
      connected: '✅ Connected, Model: {{model}}',
      connectFailed: '❌ Failed: {{error}}',
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
      send: '发送',
      stop: '停止',
      mode: '运行模式',
      templates: '配置模板',
      home: '首页',
      configPath: '配置 / 日志路径',
      connect: '连接',
      connecting: '连接中…',
      status: '状态',
      statusDefault: '未连接',
      tplNone: '-- 选择模板 --',
      connected: '✅ 连接成功，模型: {{model}}',
      connectFailed: '❌ 连接失败: {{error}}',
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
