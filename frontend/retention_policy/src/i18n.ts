import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Retention Advice',
      subtitle:
        'How long should each table keep its partitions? Paste the ' +
        'inventory — the TTL comes from the oldest partition anyone ' +
        'still reads plus a grace, archive and purge candidates come ' +
        'back with the gigabytes they free, and the same inventory ' +
        'always yields the same advice.',
      data_label: 'Partition inventory (table,partition,size_gb,last_access)',
      data_ph: 'table,partition,size_gb,last_access\ndwd.orders,dt=2026-10-29,12.5,2026-10-30',
      active_label: 'Active window (days)',
      run_btn: 'Advise retention',
      clear_btn: 'Clear',
      empty_input: 'Paste the partition inventory first.',
      report_ph: '▶ Per-table TTLs and candidates appear here.',
      llm_label: 'LLM cleanup proposal (needs an API key)',
      home: 'Home',
      running: 'Advising…',
    },
  },
  zh: {
    translation: {
      title: '生命周期建议',
      subtitle:
        '每张表的分区该留多久？粘贴分区清单 — TTL 取仍有人读的最老分区' +
        '年龄加余量，可归档/可清理分区连同释放空间一并给出，同清单必得' +
        '同建议。',
      data_label: '分区清单（table,partition,size_gb,last_access）',
      data_ph: 'table,partition,size_gb,last_access\ndwd.orders,dt=2026-10-29,12.5,2026-10-30',
      active_label: '活跃窗口（天）',
      run_btn: '生成建议',
      clear_btn: '清空',
      empty_input: '请先粘贴分区清单。',
      report_ph: '▶ 逐表 TTL 与候选清单在此显示。',
      llm_label: 'LLM 清理提案（需 API key）',
      home: '首页',
      running: '计算中…',
    },
  },
}

export default initI18n(resources)
