import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'DB Diagnosis',
      subtitle:
        'What is the database doing right now? Paste a status snapshot ' +
        '(JSON with max_connections, threads, CPU, lock waits, ' +
        'deadlocks, slow queries — every section optional) — findings ' +
        'come back ranked: pool pressure, thread storms, lock waits ' +
        'with the worst blocking pairs, deadlocks, slow hotspots and ' +
        'CPU saturation, each with a prescription. No live connection.',
      snapshot_label: 'Status snapshot (JSON)',
      snapshot_ph: '{"variables":{"max_connections":500},"status":{"threads_connected":480,...}}',
      run_btn: 'Diagnose',
      clear_btn: 'Clear',
      empty_input: 'Paste the snapshot first.',
      report_ph: '▶ Ranked findings with prescriptions appear here.',
      llm_label: 'LLM incident note (needs an API key)',
      home: 'Home',
      running: 'Diagnosing…',
    },
  },
  zh: {
    translation: {
      title: '数据库运行诊断',
      subtitle:
        '数据库现在怎么了？粘贴状态快照（JSON：max_connections、线程数、' +
        'CPU、锁等待、死锁、慢查询，各节均可选）— 按严重度返回发现：' +
        '连接池吃紧、线程风暴、长锁等待（附最严重阻塞对）、死锁、' +
        '慢查询热点与 CPU 饱和，每条附处方。不连库。',
      snapshot_label: '状态快照（JSON）',
      snapshot_ph: '{"variables":{"max_connections":500},"status":{"threads_connected":480,...}}',
      run_btn: '诊断',
      clear_btn: '清空',
      empty_input: '请先粘贴快照。',
      report_ph: '▶ 按严重度排序的发现与处方在此显示。',
      llm_label: 'LLM 事故通报（需 API key）',
      home: '首页',
      running: '诊断中…',
    },
  },
}

export default initI18n(resources)
