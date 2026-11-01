import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Asset Value',
      subtitle:
        'Which tables are core and which are dead weight? Paste the ' +
        'inventory (CSV or JSON rows: table, size_gb, access_cnt_30d, ' +
        'last_access, downstream_cnt) — every asset comes back with a ' +
        'transparent score from access, dependencies and recency, a ' +
        'tier (core/common/edge/idle) and a value x cost quadrant. No ' +
        'database connection.',
      inventory_label: 'Asset inventory (CSV or JSON)',
      inventory_ph:
        'table,size_gb,access_cnt_30d,last_access,downstream_cnt\ndwd.orders,900,420,2026-10-30,6',
      run_btn: 'Grade',
      clear_btn: 'Clear',
      empty_input: 'Paste the inventory first.',
      report_ph: '▶ Tiers and quadrants appear here.',
      llm_label: 'LLM grading note (needs an API key)',
      home: 'Home',
      running: 'Grading…',
    },
  },
  zh: {
    translation: {
      title: '资产价值评估',
      subtitle:
        '哪些表是核心、哪些在白占存储？粘贴资产清单（CSV 或 JSON：' +
        'table, size_gb, access_cnt_30d, last_access, downstream_cnt）— ' +
        '每个资产按访问/依赖/新近度透明打分，分层核心/常用/边缘/闲置，' +
        '并给出价值×成本象限。不连数据库。',
      inventory_label: '资产清单（CSV 或 JSON）',
      inventory_ph:
        'table,size_gb,access_cnt_30d,last_access,downstream_cnt\ndwd.orders,900,420,2026-10-30,6',
      run_btn: '评估',
      clear_btn: '清空',
      empty_input: '请先粘贴资产清单。',
      report_ph: '▶ 分层与象限在此显示。',
      llm_label: 'LLM 评估通报（需 API key）',
      home: '首页',
      running: '评估中…',
    },
  },
}

export default initI18n(resources)
