import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Incident Review',
      subtitle:
        'The numbers in a postmortem are usually guessed. Paste the ' +
        'incident event log — time, kind (impact / alert / action / ' +
        'comm / recovery), text — and the timeline comes back with ' +
        'MTTD, MTTA and MTTR computed from what was written down, ' +
        'silent windows named.',
      data_label: 'Event log (time,kind,text)',
      data_ph: 'time,kind,text\n02:00,impact,report blank\n02:25,alert,timeout fired',
      run_btn: 'Review incident',
      clear_btn: 'Clear',
      empty_input: 'Paste the event log first.',
      report_ph: '▶ The timeline and durations appear here.',
      llm_label: 'LLM postmortem draft (needs an API key)',
      home: 'Home',
      running: 'Reviewing…',
    },
  },
  zh: {
    translation: {
      title: '事故复盘',
      subtitle:
        '复盘里的数字多半靠回忆。粘贴事故事件日志 — time、kind（impact / ' +
        'alert / action / comm / recovery）、text — 时间线连同发现、' +
        '响应、恢复三个用时按记录算出，静默窗口点名。',
      data_label: '事件日志（time,kind,text）',
      data_ph: 'time,kind,text\n02:00,impact,报表空白\n02:25,alert,超时告警',
      run_btn: '开始复盘',
      clear_btn: '清空',
      empty_input: '请先粘贴事件日志。',
      report_ph: '▶ 时间线与用时指标在此显示。',
      llm_label: 'LLM 复盘草稿（需 API key）',
      home: '首页',
      running: '复盘中…',
    },
  },
}

export default initI18n(resources)
