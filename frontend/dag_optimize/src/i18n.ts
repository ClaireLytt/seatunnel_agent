import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'DAG Optimizer',
      subtitle:
        'Where does the schedule waste time? Paste the task dependency ' +
        'graph (JSON tasks/edges or "a -> b" lines, optional durations) — ' +
        'redundant serial edges are found by transitive reduction, tasks ' +
        'are layered into parallel waves, and the duration-weighted ' +
        'critical path bounds the ideal speedup. Deterministic, no ' +
        'scheduler connection.',
      file_label: 'DAG file path',
      file_ph: 'Task DAG (.json or text lines), e.g. examples/dagopt_demo/dag.json',
      run_btn: 'Analyze file',
      text_acc: 'Analyze pasted DAG',
      text_label: 'JSON tasks/edges or "a -> b" lines',
      text_ph:
        '{"tasks":[{"name":"clean","deps":["extract"],"duration":5}, ...]}\n' +
        'or one edge per line:  extract -> clean',
      run_text_btn: 'Analyze text',
      clear_btn: 'Clear',
      empty_input: 'Provide the DAG file or paste the graph first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ Redundant edges, parallel waves and the critical path appear here.',
      home: 'Home',
      running: 'Analyzing…',
    },
  },
  zh: {
    translation: {
      title: 'DAG 依赖优化',
      subtitle:
        '调度在哪儿浪费时间？粘贴任务依赖图（JSON tasks/edges 或 ' +
        '"a -> b" 文本行，任务可带时长）— 传递归约找出冗余串行边，' +
        'Kahn 分层给出可并行的批次，按时长加权的关键路径决定理想加速比。' +
        '确定性分析，不连调度器。',
      file_label: 'DAG 文件路径',
      file_ph: '任务依赖图 (.json 或文本行)，如 examples/dagopt_demo/dag.json',
      run_btn: '分析文件',
      text_acc: '用粘贴的依赖图分析',
      text_label: 'JSON tasks/edges 或 "a -> b" 文本行',
      text_ph:
        '{"tasks":[{"name":"clean","deps":["extract"],"duration":5}, ...]}\n' +
        '或每行一条边：  extract -> clean',
      run_text_btn: '用文本分析',
      clear_btn: '清空',
      empty_input: '请先填写 DAG 文件路径或粘贴依赖图。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 冗余依赖边、并行批次与关键路径在此显示。',
      home: '首页',
      running: '分析中…',
    },
  },
}

export default initI18n(resources)
