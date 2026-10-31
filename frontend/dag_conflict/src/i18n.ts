import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'DAG Conflicts',
      subtitle:
        'Can these DAGs share the cluster? Describe the scenario in JSON ' +
        '(capacity + per-DAG tasks with duration, slots, memory and ' +
        'written tables, plus start offsets) — the timeline is simulated ' +
        'for over-capacity windows and cross-DAG write-write conflicts, ' +
        'and the stagger suggestion is verified by re-simulation. ' +
        'Deterministic, no scheduler connection.',
      file_label: 'Scenario file path',
      file_ph: 'scenario JSON, e.g. examples/dagconflict_demo/scenario.json',
      run_btn: 'Simulate file',
      place_label: 'Admission check: DAG name (optional)',
      place_ph: 'e.g. etl_users — sweeps start offsets for the best slot',
      text_acc: 'Simulate pasted scenario',
      text_label: 'Scenario JSON',
      text_ph:
        '{"capacity":{"slots":10,"memory_gb":50},"dags":[{"name":"etl_a",' +
        '"start":0,"tasks":[{"name":"t1","duration":10,"slots":4,' +
        '"writes":["dws.sales"]}, ...]}, ...]}',
      run_text_btn: 'Simulate text',
      clear_btn: 'Clear',
      empty_input: 'Provide the scenario file or paste the JSON first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ Over-capacity windows, write conflicts and the stagger suggestion appear here.',
      home: 'Home',
      running: 'Simulating…',
    },
  },
  zh: {
    translation: {
      title: '并发冲突检测',
      subtitle:
        '这些 DAG 能同时跑吗？用 JSON 描述场景（集群容量 + 各 DAG 的任务' +
        '时长/槽位/内存/写入表与启动偏移）— 推演时间线找出超容时间窗与' +
        '跨 DAG 写写冲突，错峰建议经重新模拟验证后给出。确定性推演，' +
        '不连调度器。',
      file_label: '场景文件路径',
      file_ph: '场景 JSON，如 examples/dagconflict_demo/scenario.json',
      run_btn: '模拟文件',
      place_label: '准入检查：DAG 名（可选）',
      place_ph: '如 etl_users — 扫描候选起点选最优错峰位',
      text_acc: '用粘贴的场景模拟',
      text_label: '场景 JSON',
      text_ph:
        '{"capacity":{"slots":10,"memory_gb":50},"dags":[{"name":"etl_a",' +
        '"start":0,"tasks":[{"name":"t1","duration":10,"slots":4,' +
        '"writes":["dws.sales"]}, ...]}, ...]}',
      run_text_btn: '用文本模拟',
      clear_btn: '清空',
      empty_input: '请先填写场景文件路径或粘贴 JSON。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 超容时间窗、写写冲突与错峰建议在此显示。',
      home: '首页',
      running: '模拟中…',
    },
  },
}

export default initI18n(resources)
