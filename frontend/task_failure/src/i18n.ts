import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Task Failure',
      subtitle:
        'Why did the overnight jobs fail? Paste the failed-task export (CSV ' +
        'or JSON list with task, error text, retries, final status) — ' +
        'errors come back classified, identical root causes clustered ' +
        'into one group with members and a sample error, and retry ' +
        'effectiveness judged (transient / futile), each class with a ' +
        'prescription. No scheduler connection.',
      export_label: 'Failed-task export (CSV or JSON)',
      export_ph: '[{"task":"dwd_orders","error":"FileNotFoundException...","retries":3}]',
      run_btn: 'Attribute',
      clear_btn: 'Clear',
      empty_input: 'Paste the export first.',
      report_ph: '▶ Root-cause clusters with retry verdicts appear here.',
      llm_label: 'LLM failure note (needs an API key)',
      home: 'Home',
      running: 'Attributing…',
    },
  },
  zh: {
    translation: {
      title: '任务失败归因',
      subtitle:
        '昨晚的任务为什么挂？粘贴失败任务导出（CSV 或 JSON：task、错误' +
        '文本、重试次数、最终状态）— 错误自动归类，同根因聚成一组（附' +
        '成员与错误样例），并判定重试有效性（瞬态/无效），每类附处方。' +
        '不连调度器。',
      export_label: '失败任务导出（CSV 或 JSON）',
      export_ph: '[{"task":"dwd_orders","error":"FileNotFoundException...","retries":3}]',
      run_btn: '归因',
      clear_btn: '清空',
      empty_input: '请先粘贴导出。',
      report_ph: '▶ 同根因聚类与重试判定在此显示。',
      llm_label: 'LLM 失败通报（需 API key）',
      home: '首页',
      running: '归因中…',
    },
  },
}

export default initI18n(resources)
