import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Alert Storm',
      subtitle:
        'How many pages were real? Paste the alert export (CSV or JSON: ' +
        'ts, source, title, level) — alerts cluster by normalized ' +
        'signature with the dedup ratio up front, plus storm windows, ' +
        'flapping signatures (suppression candidates) and noisy ' +
        'sources, each with a prescription. No alerting-system ' +
        'connection.',
      export_label: 'Alert export (CSV or JSON)',
      export_ph:
        '[{"ts":"2026-10-31 02:10:00","source":"scheduler","title":"...","level":"error"}]',
      run_btn: 'Digest',
      clear_btn: 'Clear',
      empty_input: 'Paste the export first.',
      report_ph: '▶ Clusters, storms and suppression hints appear here.',
      llm_label: 'LLM handover digest (needs an API key)',
      home: 'Home',
      running: 'Digesting…',
    },
  },
  zh: {
    translation: {
      title: '告警风暴聚合',
      subtitle:
        '这些告警里有几件真事？粘贴告警导出（CSV 或 JSON：ts、source、' +
        'title、level）— 按归一化签名聚类并给出降噪倍数，另检出风暴' +
        '窗口、横跳签名（抑制候选）与吵闹来源，每条附处方。' +
        '不连告警系统。',
      export_label: '告警导出（CSV 或 JSON）',
      export_ph:
        '[{"ts":"2026-10-31 02:10:00","source":"scheduler","title":"...","level":"error"}]',
      run_btn: '聚合',
      clear_btn: '清空',
      empty_input: '请先粘贴导出。',
      report_ph: '▶ 聚类、风暴与抑制建议在此显示。',
      llm_label: 'LLM 交接摘要（需 API key）',
      home: '首页',
      running: '聚合中…',
    },
  },
}

export default initI18n(resources)
