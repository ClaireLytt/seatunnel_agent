import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

// Language follows the hub's st-lang cookie (set on the landing page).
function langFromCookie(): 'en' | 'zh' {
  const m = document.cookie.match(/(?:^|;\s*)st-lang=([^;]+)/)
  return m && decodeURIComponent(m[1]).startsWith('zh') ? 'zh' : 'en'
}

const EDITOR_PH_EN = `- id: MY1
  title: my first case
  tags: [full, sqlite]
  page: /datacompare
  steps:
    - ai: describe the action in plain language — no selectors needed
  expect:
    - ai_judge: describe what you expect to see`

const EDITOR_PH_ZH = `- id: MY1
  title: 我的第一条用例
  tags: [full, sqlite]
  page: /datacompare
  steps:
    - ai: 用中文描述要做的操作即可,无需任何选择器
  expect:
    - ai_judge: 用中文描述预期看到什么`

const resources = {
  en: {
    translation: {
      title: 'UI Testing Agent',
      subtitle:
        'Browser-driven regression for the agent pages. The app under test runs on its own port (7912+) and never touches this session.',
      suite: 'Suite',
      agent: 'Agent (overrides suite)',
      agentAll: 'All agents',
      cases: 'Specific cases (optional, e.g. A5 B3; overrides the suite)',
      noLlm: 'Skip LLM cases (0 tokens)',
      run: 'Run',
      running: 'Running…',
      progress: 'Progress',
      results: 'Results',
      report: 'Report',
      download: 'Download report',
      starting: 'Starting the app under test and seeding data…',
      elapsed: 'elapsed',
      editorTitle: 'Add a case (no code — saved to config/uitest_cases/)',
      editorSave: 'Validate & Save',
      editorSaved: 'Saved: {{ids}} → {{path}} — run it via "Specific cases" above',
      editorPh: EDITOR_PH_EN,
      home: 'Home',
      history: 'Past runs',
      view: 'View',
    },
  },
  zh: {
    translation: {
      title: 'UI 测试 Agent',
      subtitle: '驱动真实浏览器回归各 Agent 页面。被测应用运行在独立端口 7912+,不影响当前会话。',
      suite: '套件',
      agent: '按 Agent 测 (优先于套件)',
      agentAll: '全部 Agent',
      cases: '指定用例 (可选,如 A5 B3;优先于套件)',
      noLlm: '跳过 LLM 用例 (零 token)',
      run: '运行',
      running: '运行中…',
      progress: '进度',
      results: '结果',
      report: '报告',
      download: '下载报告',
      starting: '启动被测应用并种子数据…',
      elapsed: '耗时',
      editorTitle: '添加用例 (零代码 — 保存到 config/uitest_cases/)',
      editorSave: '校验并保存',
      editorSaved: '已保存: {{ids}} → {{path}} — 在上方"指定用例"里填 id 即可运行',
      editorPh: EDITOR_PH_ZH,
      home: '首页',
      history: '历史运行',
      view: '查看',
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
