import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Contract Draft',
      subtitle:
        'Nobody writes the first data contract by hand. Paste the ' +
        'CREATE TABLE DDL — the draft promises what each table already ' +
        'keeps: columns with types, the partition layout, the comment ' +
        'discipline — and the YAML pastes straight into Contract Check.',
      sql_label: 'CREATE TABLE DDL',
      sql_ph: 'CREATE TABLE ods.t ( ... ) PARTITIONED BY (dt STRING);',
      tables_label: 'Only these tables (comma-separated, optional)',
      tables_ph: 'e.g. ods.user_info',
      types_label: 'Pin column types',
      strict_label: 'Freeze shape (allow_extra_columns: false)',
      run_btn: 'Draft contract',
      clear_btn: 'Clear',
      empty_input: 'Paste the CREATE TABLE DDL first.',
      report_ph: '▶ The per-table promises and contract.yaml appear here.',
      llm_label: 'LLM tightening suggestions (needs an API key)',
      home: 'Home',
      running: 'Drafting…',
    },
  },
  zh: {
    translation: {
      title: '契约草稿生成',
      subtitle:
        '第一份数据契约没人愿意手写。粘贴 CREATE TABLE DDL — 草稿只承诺' +
        '各表当前已做到的：列与类型、分区布局、注释纪律 — 生成的 YAML ' +
        '可直接粘到契约体检上闸。',
      sql_label: 'CREATE TABLE DDL',
      sql_ph: 'CREATE TABLE ods.t ( ... ) PARTITIONED BY (dt STRING);',
      tables_label: '限定表（逗号分隔，可选）',
      tables_ph: '如 ods.user_info',
      types_label: '固定列类型',
      strict_label: '冻结结构（allow_extra_columns: false）',
      run_btn: '生成契约草稿',
      clear_btn: '清空',
      empty_input: '请先粘贴 CREATE TABLE DDL。',
      report_ph: '▶ 逐表承诺与 contract.yaml 在此显示。',
      llm_label: 'LLM 收紧建议（需 API key）',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
