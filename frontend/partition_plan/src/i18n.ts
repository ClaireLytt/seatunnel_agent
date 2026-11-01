import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Partition Plan',
      subtitle:
        'A new table needs its partition key before the first byte ' +
        'lands. Paste a data sample and the queries that will hit it — ' +
        'every column is scored by filter share, time shape and ' +
        'cardinality band, the DDL clause comes back ready, and hot id ' +
        'columns get a bucketing suggestion instead.',
      data_label: 'Data sample (CSV with header, or JSONL)',
      data_ph: 'order_id,order_date,amount\n1,2026-10-01,12.5',
      queries_label: 'Query workload (SQL that will hit the table)',
      queries_ph: "SELECT ... WHERE order_date = '2026-10-30';",
      run_btn: 'Plan partitions',
      clear_btn: 'Clear',
      empty_input: 'Paste the sample and the workload first.',
      report_ph: '▶ Ranked candidates and the DDL clause appear here.',
      llm_label: 'LLM plan review (needs an API key)',
      home: 'Home',
      running: 'Scoring…',
    },
  },
  zh: {
    translation: {
      title: '分区键选型',
      subtitle:
        '新表落第一个字节之前就该定好分区键。粘贴数据样例和将要打在它' +
        '上面的查询 — 逐列按过滤频率、时间形、基数甜区打分，DDL 子句' +
        '现成；高基数热 id 列改配分桶建议。',
      data_label: '数据样例（CSV 带表头，或 JSONL）',
      data_ph: 'order_id,order_date,amount\n1,2026-10-01,12.5',
      queries_label: '查询负载（将要打在这张表上的 SQL）',
      queries_ph: "SELECT ... WHERE order_date = '2026-10-30';",
      run_btn: '开始选型',
      clear_btn: '清空',
      empty_input: '请先粘贴样例与查询负载。',
      report_ph: '▶ 候选排名与 DDL 子句在此显示。',
      llm_label: 'LLM 选型评审（需 API key）',
      home: '首页',
      running: '打分中…',
    },
  },
}

export default initI18n(resources)
