import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Flink Diagnosis',
      subtitle:
        'Why is the Flink job struggling? Paste a job snapshot (JSON ' +
        'with checkpoints, operator backpressure and watermark lag, ' +
        'restart counts — every section optional) — findings come back ' +
        'ranked: checkpoint failures and blow-ups, alignment-dominated ' +
        'checkpoints, backpressured operators, watermark lag and ' +
        'restart churn, each with a prescription. No cluster connection.',
      snapshot_label: 'Job snapshot (JSON)',
      snapshot_ph: '{"job":"sync-orders","checkpoints":[...],"operators":[...],"restarts":...}',
      run_btn: 'Diagnose',
      clear_btn: 'Clear',
      empty_input: 'Paste the snapshot first.',
      report_ph: '▶ Ranked findings with prescriptions appear here.',
      llm_label: 'LLM ops note (needs an API key)',
      home: 'Home',
      running: 'Diagnosing…',
    },
  },
  zh: {
    translation: {
      title: 'Flink 作业诊断',
      subtitle:
        'Flink 作业为什么难受？粘贴作业快照（JSON：checkpoints、算子' +
        '背压与 watermark 滞后、重启次数，各节可选）— 按严重度返回' +
        '发现：checkpoint 失败/时长暴涨/对齐主导、背压算子、watermark ' +
        '滞后、频繁重启，每条附处方。不连集群。',
      snapshot_label: '作业快照（JSON）',
      snapshot_ph: '{"job":"sync-orders","checkpoints":[...],"operators":[...],"restarts":...}',
      run_btn: '诊断',
      clear_btn: '清空',
      empty_input: '请先粘贴快照。',
      report_ph: '▶ 按严重度排序的发现与处方在此显示。',
      llm_label: 'LLM 运维通报（需 API key）',
      home: '首页',
      running: '诊断中…',
    },
  },
}

export default initI18n(resources)
