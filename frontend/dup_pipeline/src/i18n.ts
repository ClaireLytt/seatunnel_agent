import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Dup Pipelines',
      subtitle:
        'Two teams building the same aggregate from the same sources is ' +
        'double compute and two numbers that drift apart. Paste the ' +
        'pipeline SQL — targets reading the same sources with the same ' +
        'output math grade high, subset-derivation candidates and hot ' +
        'sources missing a middle layer follow.',
      sql_label: 'Pipeline SQL (INSERT / CREATE statements)',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      fanout_label: 'Fan-out threshold (direct readers)',
      run_btn: 'Detect duplicates',
      clear_btn: 'Clear',
      empty_input: 'Paste the pipeline SQL first.',
      report_ph: '▶ Graded duplicate-build findings appear here.',
      llm_label: 'LLM consolidation plan (needs an API key)',
      home: 'Home',
      running: 'Detecting…',
    },
  },
  zh: {
    translation: {
      title: '重复建设检测',
      subtitle:
        '两个团队从同样的源各建一张同样的汇总表，等于双倍算力加两个会漂' +
        '移的口径。粘贴流水线 SQL — 同源且输出口径一致记高危，子集派生' +
        '候选与高扇出缺中间层随后给出。',
      sql_label: '流水线 SQL（INSERT / CREATE 语句）',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      fanout_label: '扇出阈值（直读目标数）',
      run_btn: '开始检测',
      clear_btn: '清空',
      empty_input: '请先粘贴流水线 SQL。',
      report_ph: '▶ 重复建设分级发现在此显示。',
      llm_label: 'LLM 收敛方案（需 API key）',
      home: '首页',
      running: '检测中…',
    },
  },
}

export default initI18n(resources)
