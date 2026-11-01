import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Watermark Plan',
      subtitle:
        '"How many seconds of out-of-orderness?" is usually answered by ' +
        'guessing. Paste observed events — event_time and arrival_time ' +
        '— and the lateness distribution answers instead: a measured ' +
        'bound with the Flink snippets, clock skew and stragglers ' +
        'called out.',
      data_label: 'Observed events (event_time,arrival_time)',
      data_ph: 'event_time,arrival_time\n10:00:00,10:00:02',
      run_btn: 'Plan watermark',
      clear_btn: 'Clear',
      empty_input: 'Paste the observed events first.',
      report_ph: '▶ The measured bound and snippets appear here.',
      llm_label: 'LLM watermark review (needs an API key)',
      home: 'Home',
      running: 'Measuring…',
    },
  },
  zh: {
    translation: {
      title: '水位线选型',
      subtitle:
        '"乱序容忍设几秒"通常靠拍脑袋。粘贴观测事件 — event_time 与 ' +
        'arrival_time — 用迟到分布来回答：实测的乱序容忍 + Flink 配置' +
        '片段，时钟漂移与掉队者一并点名。',
      data_label: '观测事件（event_time,arrival_time）',
      data_ph: 'event_time,arrival_time\n10:00:00,10:00:02',
      run_btn: '开始选型',
      clear_btn: '清空',
      empty_input: '请先粘贴观测事件。',
      report_ph: '▶ 实测乱序容忍与配置片段在此显示。',
      llm_label: 'LLM 水位线评审（需 API key）',
      home: '首页',
      running: '测量中…',
    },
  },
}

export default initI18n(resources)
