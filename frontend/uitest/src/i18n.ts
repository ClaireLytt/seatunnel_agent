import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

// Language follows the hub's st-lang cookie (set on the landing page).
function langFromCookie(): 'en' | 'zh' {
  const m = document.cookie.match(/(?:^|;\s*)st-lang=([^;]+)/)
  return m && decodeURIComponent(m[1]).startsWith('zh') ? 'zh' : 'en'
}

const resources = {
  en: {
    translation: {
      title: 'UI Testing Agent',
      subtitle:
        'Browser-driven regression for the agent pages. The app under test runs on its own port (7912+) and never touches this session.',
      suite: 'Suite',
      agent: 'Agent (overrides suite)',
      cases: 'Specific cases (optional, e.g. A5 B3; overrides the suite)',
      noLlm: 'Skip LLM cases (0 tokens)',
      run: 'Run',
      progress: 'Progress',
      download: 'Download report',
      starting: 'Starting the app under test and seeding data…',
      editorTitle: 'Add a case (no code)',
      editorSave: 'Validate & Save',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: 'UI 测试 Agent',
      subtitle: '驱动真实浏览器回归各 Agent 页面。被测应用运行在独立端口 7912+,不影响当前会话。',
      suite: '套件',
      agent: '按 Agent 测 (优先于套件)',
      cases: '指定用例 (可选,如 A5 B3;优先于套件)',
      noLlm: '跳过 LLM 用例 (零 token)',
      run: '运行',
      progress: '进度',
      download: '下载报告',
      starting: '启动被测应用并种子数据…',
      editorTitle: '添加用例 (零代码)',
      editorSave: '校验并保存',
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
