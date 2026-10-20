import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { langFromCookie } from '@shared/lang'

// Copy ported from the Gradio page's _I18N
// (seatunnel_agent/agents/ai/llm_cost/ui.py) — title split into
// title+subtitle. Chart / price-table / CSV keys land with ticket 03.
const resources = {
  en: {
    translation: {
      title: 'LLM Cost',
      subtitle:
        'Cost & usage dashboard over the cross-agent LLM call log — every LLMClient.chat call is priced against an approximate catalog you can override in ~/.seatunnel-agent/pricing.yaml.',
      daysLabel: 'Window (days)',
      budgetLabel: 'Budget (USD, optional)',
      refreshBtn: 'Refresh',
      budgetOk: '✅ Within budget: {{cost}} of {{budget}} used ({{pct}})',
      budgetOver: '🔴 Over budget: {{cost}} spent vs {{budget}} ({{pct}})',
      noData: 'No data to chart in this window.',
      loading: 'Loading…',
      home: 'Home',
      chartCost: 'Cost per day (stacked by model)',
      chartTokens: 'Tokens by model',
      budgetLine: 'daily budget',
      priceAcc: 'Price catalog',
      priceNote: 'Override file: ',
      pricePrefix: 'Model prefix',
      priceInput: 'Input $/M',
      priceOutput: 'Output $/M',
      priceSource: 'Source',
      csvBtn: 'Download CSV',
    },
  },
  zh: {
    translation: {
      title: 'LLM 成本观测',
      subtitle:
        '基于全平台 LLM 调用日志的成本用量看板 — 每次 LLMClient.chat 调用按近似价格表计价,价格可在 ~/.seatunnel-agent/pricing.yaml 覆盖。',
      daysLabel: '时间窗(天)',
      budgetLabel: '预算(USD,可选)',
      refreshBtn: '刷新',
      budgetOk: '✅ 预算内:已用 {{cost}} / {{budget}}({{pct}})',
      budgetOver: '🔴 超出预算:已用 {{cost}},预算 {{budget}}({{pct}})',
      noData: '该时间窗内没有可作图的数据。',
      loading: '加载中…',
      home: '首页',
      chartCost: '按日成本(按模型堆叠)',
      chartTokens: '按模型 tokens',
      budgetLine: '日均预算',
      priceAcc: '价格表',
      priceNote: '覆盖文件: ',
      pricePrefix: '模型前缀',
      priceInput: '输入 $/M',
      priceOutput: '输出 $/M',
      priceSource: '来源',
      csvBtn: '下载明细 CSV',
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
