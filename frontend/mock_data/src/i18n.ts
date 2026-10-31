import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Mock Data',
      subtitle:
        'Rows that look like production without being production. Paste ' +
        'a sample — ranges, date windows, value distributions and null ' +
        'rates carry over; phones, IDs, emails and names are synthesized ' +
        'fakes that never copy a real value. Same sample and seed, same ' +
        'rows.',
      data_label: 'Sample rows (CSV with header, or JSONL)',
      data_ph: 'user_id,mobile,amount\n1001,13812340001,12.50',
      count_label: 'Rows to generate',
      seed_label: 'Seed',
      run_btn: 'Generate rows',
      clear_btn: 'Clear',
      download_btn: 'Download CSV',
      empty_input: 'Paste the sample rows first.',
      report_ph: '▶ Column strategies and generated rows appear here.',
      llm_label: 'LLM dataset note (needs an API key; strategies only)',
      home: 'Home',
      running: 'Generating…',
    },
  },
  zh: {
    translation: {
      title: '测试数据生成',
      subtitle:
        '长得像生产数据但不是生产数据。粘贴样例 — 数值区间、日期窗口、' +
        '值分布与空值率全部保留；手机号、身份证、邮箱、姓名现场合成，' +
        '绝不复制真实值。同样例同种子必得同结果。',
      data_label: '样例行（CSV 带表头，或 JSONL）',
      data_ph: 'user_id,mobile,amount\n1001,13812340001,12.50',
      count_label: '生成行数',
      seed_label: '种子',
      run_btn: '生成数据',
      clear_btn: '清空',
      download_btn: '下载 CSV',
      empty_input: '请先粘贴样例行。',
      report_ph: '▶ 逐列策略与生成样例在此显示。',
      llm_label: 'LLM 数据集说明（需 API key,只发策略）',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
