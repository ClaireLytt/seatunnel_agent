import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Rerun Planner',
      subtitle:
        'A task failed — what is the minimal set to re-run? Point at the ' +
        'task dependency graph (JSON tasks/edges or "a -> b" lines) and ' +
        'name the failed tasks: the plan is their downstream closure in ' +
        'topological batches, with upstream outputs kept, sibling branches ' +
        'untouched and the blast radius stated. Deterministic, no ' +
        'scheduler connection.',
      file_label: 'DAG file path',
      file_ph: 'Task DAG (.json or text lines), e.g. examples/rerun_demo/dag.json',
      failed_label: 'Failed tasks',
      failed_ph: 'comma-separated, e.g. clean_orders, clean_users',
      ok_label: 'Succeeded tasks (optional)',
      ok_ph: 'comma-separated — flagged if their inputs went stale',
      cmd_label: 'Command template (optional)',
      cmd_ph: 'e.g. airflow tasks run {task}',
      run_btn: 'Plan file',
      text_acc: 'Plan pasted DAG',
      text_label: 'JSON tasks/edges or "a -> b" lines',
      text_ph: '{"tasks":[{"name":"clean","deps":["extract"]}, ...]}',
      run_text_btn: 'Plan text',
      clear_btn: 'Clear',
      empty_input: 'Provide the DAG file or paste the graph first.',
      empty_failed: 'Name the failed tasks first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ The minimal rerun batches and the blast radius appear here.',
      home: 'Home',
      running: 'Planning…',
    },
  },
  zh: {
    translation: {
      title: '任务重跑规划',
      subtitle:
        '任务失败了 — 最少要重跑哪些？指向任务依赖图（JSON tasks/edges ' +
        '或 "a -> b" 文本行），填上失败任务名：计划即失败任务的下游闭包，' +
        '按拓扑批次给出；上游产出保留、兄弟分支不动，并给出影响面。' +
        '确定性计划，不连调度器。',
      file_label: 'DAG 文件路径',
      file_ph: '任务依赖图 (.json 或文本行)，如 examples/rerun_demo/dag.json',
      failed_label: '失败任务',
      failed_ph: '逗号分隔，如 clean_orders, clean_users',
      ok_label: '已成功任务（可选）',
      ok_ph: '逗号分隔 — 输入失效的会被标记',
      cmd_label: '命令模板（可选）',
      cmd_ph: '如 airflow tasks run {task}',
      run_btn: '生成计划',
      text_acc: '用粘贴的依赖图生成计划',
      text_label: 'JSON tasks/edges 或 "a -> b" 文本行',
      text_ph: '{"tasks":[{"name":"clean","deps":["extract"]}, ...]}',
      run_text_btn: '用文本生成',
      clear_btn: '清空',
      empty_input: '请先填写 DAG 文件路径或粘贴依赖图。',
      empty_failed: '请先填写失败任务名。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 最小重跑批次与影响面在此显示。',
      home: '首页',
      running: '规划中…',
    },
  },
}

export default initI18n(resources)
