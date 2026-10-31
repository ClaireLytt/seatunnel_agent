import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'DQC Rule Draft',
      subtitle:
        'Nobody writes the first rule file by hand. Paste a sample of ' +
        'the table — the draft promises what the data already keeps: a ' +
        'row-count guard, null caps with head-room, unique checks on ' +
        'key-shaped columns, enum pins on low-cardinality ones — and ' +
        'the YAML loads straight into the DQC runner.',
      data_label: 'Table sample (CSV with header, or JSONL)',
      data_ph: 'order_id,status,amount\n1,paid,10.5',
      table_label: 'Table name',
      table_ph: 'e.g. dwd.orders',
      where_label: 'Partition filter (optional)',
      where_ph: "e.g. dt = '${yesterday_pt}'",
      run_btn: 'Draft rules',
      clear_btn: 'Clear',
      empty_input: 'Paste the sample and name the table first.',
      report_ph: '▶ The checks and rules.yaml appear here.',
      llm_label: 'LLM tightening suggestions (needs an API key)',
      home: 'Home',
      running: 'Drafting…',
    },
  },
  zh: {
    translation: {
      title: '质量规则草稿',
      subtitle:
        '第一份质量规则没人愿意手写。粘贴表的样例 — 草稿只承诺数据已做' +
        '到的：行数护栏、带余量的空值率上限、主键形列 unique、低基数列' +
        '枚举钉住 — 生成的 YAML 可直接加载进 DQC 执行器。',
      data_label: '表样例（CSV 带表头，或 JSONL）',
      data_ph: 'order_id,status,amount\n1,paid,10.5',
      table_label: '表名',
      table_ph: '如 dwd.orders',
      where_label: '分区过滤（可选）',
      where_ph: "如 dt = '${yesterday_pt}'",
      run_btn: '生成规则草稿',
      clear_btn: '清空',
      empty_input: '请先粘贴样例并填表名。',
      report_ph: '▶ 检查项与 rules.yaml 在此显示。',
      llm_label: 'LLM 收紧建议（需 API key）',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
