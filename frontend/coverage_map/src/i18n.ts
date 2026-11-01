import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Coverage Map',
      subtitle:
        'Rules exist, contracts exist — but which tables actually have ' +
        'either? Paste the DDL plus the configured gate artifacts, and ' +
        'every table shows its protection: unguarded tables named ' +
        '(hot layers first), dead gates guarding nothing flagged, the ' +
        'coverage share up front.',
      ddl_label: 'CREATE TABLE DDL',
      ddl_ph: 'CREATE TABLE dwd.orders ( ... );',
      rules_label: 'DQC rules YAML (optional with a contract)',
      rules_ph: 'version: 1\nrules:\n  - table: dwd.orders ...',
      contract_label: 'Contract YAML (optional with rules)',
      contract_ph: 'tables:\n  - name: dim.users ...',
      run_btn: 'Map coverage',
      clear_btn: 'Clear',
      empty_input: 'Paste the DDL and at least one gate artifact.',
      report_ph: '▶ The protection map appears here.',
      llm_label: 'LLM gap-closing plan (needs an API key)',
      home: 'Home',
      running: 'Mapping…',
    },
  },
  zh: {
    translation: {
      title: '质量覆盖地图',
      subtitle:
        '规则有、契约也有 — 但到底哪些表真的有闸？粘贴 DDL 和已配置的' +
        '闸工件，逐表标出防护：裸奔的表点名（热层优先）、守着空城的' +
        '死闸揪出、覆盖率放在最前。',
      ddl_label: 'CREATE TABLE DDL',
      ddl_ph: 'CREATE TABLE dwd.orders ( ... );',
      rules_label: 'DQC 规则 YAML（有契约时可不填）',
      rules_ph: 'version: 1\nrules:\n  - table: dwd.orders ...',
      contract_label: '契约 YAML（有规则时可不填）',
      contract_ph: 'tables:\n  - name: dim.users ...',
      run_btn: '生成地图',
      clear_btn: '清空',
      empty_input: '请先粘贴 DDL 与至少一个闸工件。',
      report_ph: '▶ 防护地图在此显示。',
      llm_label: 'LLM 补洞计划（需 API key）',
      home: '首页',
      running: '盘点中…',
    },
  },
}

export default initI18n(resources)
