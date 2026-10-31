import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Kafka Lag',
      subtitle:
        'Why is the consumer group behind? Paste an offset snapshot ' +
        '(JSON topics/partitions with log-end and committed offsets, ' +
        'optional consume/produce rates, or CSV rows) — findings come ' +
        'back ranked: total backlog, hot partitions, partitions that ' +
        'never catch up, stalled partitions and catch-up ETAs, each ' +
        'with a prescription. No broker connection.',
      snapshot_label: 'Consumer-group snapshot (JSON or CSV)',
      snapshot_ph: '{"group":"g-orders","topics":[{"topic":"orders","partitions":[...]}]}',
      run_btn: 'Diagnose',
      clear_btn: 'Clear',
      empty_input: 'Paste the snapshot first.',
      report_ph: '▶ Ranked findings and the top lagging partitions appear here.',
      llm_label: 'LLM ops note (needs an API key)',
      home: 'Home',
      running: 'Diagnosing…',
    },
  },
  zh: {
    translation: {
      title: 'Kafka 消费积压',
      subtitle:
        '消费组为什么落后？粘贴 offset 快照（JSON 的 topics/partitions：' +
        '末端与已提交 offset，可选消费/生产速率；或 CSV 行）— 按严重度' +
        '返回发现：总积压、热点分区、永远追不上的分区、停滞分区与追赶 ' +
        'ETA，每条附处方。不连 broker。',
      snapshot_label: '消费组快照（JSON 或 CSV）',
      snapshot_ph: '{"group":"g-orders","topics":[{"topic":"orders","partitions":[...]}]}',
      run_btn: '诊断',
      clear_btn: '清空',
      empty_input: '请先粘贴快照。',
      report_ph: '▶ 发现与积压 Top 分区在此显示。',
      llm_label: 'LLM 运维通报（需 API key）',
      home: '首页',
      running: '诊断中…',
    },
  },
}

export default initI18n(resources)
