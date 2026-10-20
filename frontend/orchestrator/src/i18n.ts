import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

// Copy carried over from the legacy Gradio page
// (seatunnel_agent/agents/ai/orchestrator/ui.py _I18N).
const resources = {
  en: {
    translation: {
      title: 'Agent Orchestrator',
      subtitle:
        'One chat entry for the whole platform — describe what you need ' +
        '(paste SQL / configs / DDL right in the message) and the LLM routes ' +
        'it to the right agents, chaining steps when needed.',
      chatPhTitle: '👋 What can I do?',
      chatPh:
        'Paste SQL / configs / DDL straight into the message — I route it to ' +
        'the right agent: review, dialect translation, impact analysis, skew ' +
        'check, formatting, config lint, schema drift, PII scan, test data…',
      chatPhChain: 'Steps chain automatically: “translate to Doris, then review the result”.',
      inputPh: 'e.g. Review this SQL and then format it: SELECT …',
      send: 'Send',
      newSession: 'New session',
      noKey:
        '⚠️ No LLM configured — suggestions only. Configure an API key on the Settings page.',
      working: '⏳ Routing & running agents…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '智能编排',
      subtitle:
        '全平台统一对话入口 — 描述你的需求(SQL / 配置 / DDL 直接贴在消息里),' +
        'LLM 自动路由到合适的 agent,需要时自动串联多步。',
      chatPhTitle: '👋 我能做什么?',
      chatPh:
        '把 SQL / 配置 / DDL 直接贴进消息,我会路由到合适的 agent:审查、' +
        '方言翻译、影响分析、倾斜检测、格式化、配置检查、Schema 漂移、' +
        'PII 扫描、测试造数…',
      chatPhChain: '支持多步串联:「翻译成 Doris,然后审查结果」。',
      inputPh: '例如:帮我审查这段 SQL 然后格式化:SELECT …',
      send: '发送',
      newSession: '新会话',
      noKey: '⚠️ 未配置 LLM — 仅能做关键词推荐。请到设置页配置 API key。',
      working: '⏳ 正在路由并执行 agent…',
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
