import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Topic Schema Diff',
      subtitle:
        'The registry rejects the publish after you hit enter; this ' +
        'page tells you before. Paste the old and new Avro record or ' +
        'JSON Schema — every field change comes back graded by ' +
        'compatibility mode, with the exact rule it breaks.',
      old_label: 'Old schema (Avro record or JSON Schema)',
      new_label: 'New schema',
      schema_ph: '{"type": "record", "name": "Order", "fields": [ ... ]}',
      mode_label: 'Compatibility mode (backward / forward / full)',
      run_btn: 'Check compatibility',
      clear_btn: 'Clear',
      empty_input: 'Paste both schema versions first.',
      report_ph: '▶ The compatibility verdict appears here.',
      llm_label: 'LLM rollout note (needs an API key)',
      home: 'Home',
      running: 'Checking…',
    },
  },
  zh: {
    translation: {
      title: '消息 Schema 对比',
      subtitle:
        '注册中心是在你按下发布之后才拒绝的；这页在那之前告诉你。粘贴' +
        '两版 Avro record 或 JSON Schema — 逐字段按兼容模式分级，' +
        '并点名各自破坏的规则。',
      old_label: '旧版 Schema（Avro record 或 JSON Schema）',
      new_label: '新版 Schema',
      schema_ph: '{"type": "record", "name": "Order", "fields": [ ... ]}',
      mode_label: '兼容模式（backward / forward / full）',
      run_btn: '检查兼容性',
      clear_btn: '清空',
      empty_input: '请先粘贴两版 Schema。',
      report_ph: '▶ 兼容性结论在此显示。',
      llm_label: 'LLM 发布通报（需 API key）',
      home: '首页',
      running: '检查中…',
    },
  },
}

export default initI18n(resources)
