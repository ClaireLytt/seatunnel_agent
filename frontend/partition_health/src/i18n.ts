import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Partition Health',
      subtitle:
        'Are the partitions themselves healthy? Paste the partition ' +
        'listing (CSV or JSON: table, partition, size_gb, optional ' +
        'rows) — per table come back date gaps (backfill holes), empty ' +
        'partitions, size skew against the median, and a surging or ' +
        'shrunken latest partition, each with a prescription. Whether ' +
        'they arrive on time is the freshness agent. No database ' +
        'connection.',
      listing_label: 'Partition listing (CSV or JSON)',
      listing_ph: 'table,partition,size_gb,rows\nods.log,dt=2026-10-29,20.1,41000000',
      run_btn: 'Check',
      clear_btn: 'Clear',
      empty_input: 'Paste the listing first.',
      report_ph: '▶ Gaps, empties, skew and surges appear here.',
      llm_label: 'LLM partition note (needs an API key)',
      home: 'Home',
      running: 'Checking…',
    },
  },
  zh: {
    translation: {
      title: '分区健康体检',
      subtitle:
        '分区本身健不健康？粘贴分区清单（CSV 或 JSON：table、partition、' +
        'size_gb，可选 rows）— 逐表返回日期断档（回刷洞）、空分区、' +
        '大小倾斜与最新分区暴涨/缩水，每条附处方。按不按时到是' +
        '新鲜度 agent 的事。不连数据库。',
      listing_label: '分区清单（CSV 或 JSON）',
      listing_ph: 'table,partition,size_gb,rows\nods.log,dt=2026-10-29,20.1,41000000',
      run_btn: '体检',
      clear_btn: '清空',
      empty_input: '请先粘贴清单。',
      report_ph: '▶ 断档/空分区/倾斜/涨缩在此显示。',
      llm_label: 'LLM 分区通报（需 API key）',
      home: '首页',
      running: '体检中…',
    },
  },
}

export default initI18n(resources)
