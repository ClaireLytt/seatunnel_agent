import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'CDC Diagnosis',
      subtitle:
        'Is the binlog sync safe? Paste a replication snapshot (JSON ' +
        'with the source binlog file/position/retention, the consumer ' +
        'coordinates, last event time and recent errors — every section ' +
        'optional) — findings come back ranked: files behind, byte lag, ' +
        'event stalls, the retention data-loss deadline, classified ' +
        'errors and broken resume points, each with a prescription. No ' +
        'database connection.',
      snapshot_label: 'Replication snapshot (JSON)',
      snapshot_ph: '{"source":{"binlog_file":"mysql-bin.000123",...},"consumer":{...}}',
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
      title: 'CDC 同步诊断',
      subtitle:
        'binlog 同步还安全吗？粘贴同步快照（JSON：源端 binlog 文件/位点/' +
        '保留期、消费端坐标、最后事件时间与近期错误，各节可选）— 按' +
        '严重度返回发现：文件落后、字节落后、事件停滞、保留期丢数倒计时、' +
        '错误分类与断点错乱，每条附处方。不连库。',
      snapshot_label: '同步快照（JSON）',
      snapshot_ph: '{"source":{"binlog_file":"mysql-bin.000123",...},"consumer":{...}}',
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
