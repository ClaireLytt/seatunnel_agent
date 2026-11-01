import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'RT Latency',
      subtitle:
        'Where does the end-to-end time go? Paste event timestamp rows ' +
        '(CSV or JSONL: event_id plus *_ts stage columns such as ' +
        'produce/ingest/process/sink; ISO or epoch-ms) — back come ' +
        'per-hop and end-to-end p50/p95/max, the dominant hop, outlier ' +
        'events above 3x the median with their worst hop, and SLA ' +
        'breach counts. No connection to anything.',
      events_label: 'Event timestamp rows (CSV or JSONL)',
      events_ph: 'event_id,produce_ts,ingest_ts,process_ts,sink_ts\ne001,...',
      sla_label: 'End-to-end SLA ms (0 = off)',
      run_btn: 'Analyze',
      clear_btn: 'Clear',
      empty_input: 'Paste the event rows first.',
      report_ph: '▶ Per-hop percentiles and outliers appear here.',
      llm_label: 'LLM latency note (needs an API key)',
      home: 'Home',
      running: 'Analyzing…',
    },
  },
  zh: {
    translation: {
      title: '实时延迟分析',
      subtitle:
        '端到端的时间花在哪一段？粘贴事件时间戳行（CSV 或 JSONL：' +
        'event_id + 各阶段 *_ts 列，如 produce/ingest/process/sink，' +
        'ISO 时间或毫秒时间戳）— 返回分段与端到端 p50/p95/max、主导段、' +
        '离群事件（> 3 倍中位数附最慢段）与 SLA 破线数。不连任何系统。',
      events_label: '事件时间戳行（CSV 或 JSONL）',
      events_ph: 'event_id,produce_ts,ingest_ts,process_ts,sink_ts\ne001,...',
      sla_label: '端到端 SLA 毫秒（0 为不检）',
      run_btn: '分析',
      clear_btn: '清空',
      empty_input: '请先粘贴事件行。',
      report_ph: '▶ 分段分位与离群事件在此显示。',
      llm_label: 'LLM 延迟通报（需 API key）',
      home: '首页',
      running: '分析中…',
    },
  },
}

export default initI18n(resources)
