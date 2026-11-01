import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Slow-Query RCA',
      subtitle:
        'Why was this run slow? Paste the execution metrics (duration, ' +
        'scan/shuffle bytes, GC and queue time, per-stage task max/median ' +
        'and spill), optionally with the history baseline jsonl — the ' +
        'likely causes come back ranked by share with evidence and a ' +
        'prescription each. Deterministic, no cluster connection.',
      metrics_label: 'Run metrics JSON',
      metrics_ph:
        '{"name":"job","duration_s":1800,"scan_bytes":...,' +
        '"stages":[{"stage":"join","task_max_s":1250,"task_median_s":110,...}]}',
      baseline_label: 'Baseline jsonl file (optional)',
      baseline_ph: 'e.g. examples/slowquery_demo/baseline.jsonl',
      run_btn: 'Diagnose',
      baseline_acc: 'Paste the baseline inline',
      baseline_text_label: 'History runs, one JSON per line',
      baseline_text_ph: '{"ts":"...","duration_s":430,"scan_bytes":405000000000}',
      clear_btn: 'Clear',
      empty_input: 'Paste the run metrics first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ Ranked causes with evidence and prescriptions appear here.',
      llm_label: 'LLM incident note (needs an API key)',
      home: 'Home',
      running: 'Diagnosing…',
    },
  },
  zh: {
    translation: {
      title: '慢查询根因',
      subtitle:
        '这次为什么慢？粘贴执行指标（耗时、扫描/shuffle 字节、GC 与排队' +
        '时间、各 stage 的 task max/median 与溢写），可选历史基线 jsonl — ' +
        '可能根因按占比排序返回，每条附证据与处方。确定性规则，不连集群。',
      metrics_label: '执行指标 JSON',
      metrics_ph:
        '{"name":"job","duration_s":1800,"scan_bytes":...,' +
        '"stages":[{"stage":"join","task_max_s":1250,"task_median_s":110,...}]}',
      baseline_label: '基线 jsonl 文件（可选）',
      baseline_ph: '如 examples/slowquery_demo/baseline.jsonl',
      run_btn: '诊断',
      baseline_acc: '粘贴基线',
      baseline_text_label: '历史运行，每行一个 JSON',
      baseline_text_ph: '{"ts":"...","duration_s":430,"scan_bytes":405000000000}',
      clear_btn: '清空',
      empty_input: '请先粘贴执行指标。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 按占比排序的根因、证据与处方在此显示。',
      llm_label: 'LLM 慢查询通报草稿（需 API key）',
      home: '首页',
      running: '诊断中…',
    },
  },
}

export default initI18n(resources)
