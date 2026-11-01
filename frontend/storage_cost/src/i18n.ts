import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Storage Cost',
      subtitle:
        'Where is the storage money going? Paste the table inventory ' +
        '(CSV/JSON with size, 30-day access, last access, downstream ' +
        'count, optional avg_file_mb), optionally with a partition ' +
        'listing — back come ranked actions: cold-tier moves, expired ' +
        'partition drops and small-file compaction, each with the GB it ' +
        'frees. No database connection.',
      inventory_label: 'Table inventory (CSV or JSON)',
      inventory_ph: 'table,size_gb,access_cnt_30d,last_access,downstream_cnt,avg_file_mb',
      partitions_label: 'Partition listing (optional)',
      partitions_ph: 'table,partition,size_gb\nods.log,dt=2024-09-01,18',
      retention_label: 'Partition retention days',
      run_btn: 'Analyze',
      clear_btn: 'Clear',
      empty_input: 'Paste the inventory first.',
      report_ph: '▶ Ranked reclaim actions appear here.',
      llm_label: 'LLM governance note (needs an API key)',
      home: 'Home',
      running: 'Analyzing…',
    },
  },
  zh: {
    translation: {
      title: '存储成本治理',
      subtitle:
        '存储的钱花在哪了？粘贴表清单（CSV/JSON：大小、30 天访问、最近' +
        '访问、下游数，可选 avg_file_mb），可选再贴分区明细 — 返回按' +
        '收益排序的动作：迁冷、清理过期分区、小文件合并，每条带预计' +
        '释放 GB。不连数据库。',
      inventory_label: '表清单（CSV 或 JSON）',
      inventory_ph: 'table,size_gb,access_cnt_30d,last_access,downstream_cnt,avg_file_mb',
      partitions_label: '分区明细（可选）',
      partitions_ph: 'table,partition,size_gb\nods.log,dt=2024-09-01,18',
      retention_label: '分区保留天数',
      run_btn: '分析',
      clear_btn: '清空',
      empty_input: '请先粘贴表清单。',
      report_ph: '▶ 按收益排序的治理动作在此显示。',
      llm_label: 'LLM 治理通报（需 API key）',
      home: '首页',
      running: '分析中…',
    },
  },
}

export default initI18n(resources)
