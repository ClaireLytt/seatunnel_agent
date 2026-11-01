import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Sample Profiler',
      subtitle:
        'Paste CSV (header row) or JSONL data rows — a deterministic ' +
        'stride sample caps the work, then every column comes back with ' +
        'its inferred kind, null and unique rates, numeric range, top ' +
        'values and format buckets, plus ranked anomaly findings with ' +
        'row numbers. No database connection.',
      data_label: 'Data rows (CSV or JSONL)',
      data_ph: 'order_id,amount,created_at\n1001,129.90,2026-10-01\n...',
      file_label: 'Data file (optional, replaces the paste)',
      file_ph: 'e.g. examples/sampleprofile_demo/orders.csv',
      maxrows_label: 'Sample cap',
      run_btn: 'Profile',
      clear_btn: 'Clear',
      empty_input: 'Paste the data rows first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ Column profiles and ranked findings appear here.',
      llm_label: 'LLM data-review note (needs an API key)',
      home: 'Home',
      running: 'Profiling…',
    },
  },
  zh: {
    translation: {
      title: '数据抽样剖析',
      subtitle:
        '粘贴 CSV（带表头）或 JSONL 数据行 — 确定性等距抽样封顶计算量，' +
        '逐列返回类型推断、空值率、唯一率、数值范围、高频值与格式桶，' +
        '异常发现按严重度排序并带行号。不连数据库。',
      data_label: '数据行（CSV 或 JSONL）',
      data_ph: 'order_id,amount,created_at\n1001,129.90,2026-10-01\n...',
      file_label: '数据文件（可选，优先于粘贴）',
      file_ph: '如 examples/sampleprofile_demo/orders.csv',
      maxrows_label: '抽样上限',
      run_btn: '剖析',
      clear_btn: '清空',
      empty_input: '请先粘贴数据行。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 列剖面与按严重度排序的发现在此显示。',
      llm_label: 'LLM 数据体检通报（需 API key）',
      home: '首页',
      running: '剖析中…',
    },
  },
}

export default initI18n(resources)
