import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Scheduling Delay Trace',
      subtitle:
        'Why did the pipeline finish late? Paste a task-instance export ' +
        '(JSON or CSV with name/start/end/deps) or point at the file — ' +
        'the critical path to the target task is computed and every hop ' +
        'is attributed to waiting vs running. Deterministic, no scheduler ' +
        'connection.',
      file_label: 'Export file path',
      file_ph: 'Task-instance export (.json/.csv), e.g. examples/slatrace_demo/run.json',
      target_label: 'Target task (optional)',
      target_ph: 'Default: the task that ends last',
      deadline_label: 'SLA deadline (optional)',
      deadline_ph: 'e.g. 2024-05-01 05:00:00',
      trace_btn: 'Trace file',
      text_acc: 'Trace pasted export',
      text_label: 'JSON / CSV export',
      text_ph: '[{"name":"a","start":"...","end":"...","deps":[]}, ...]',
      trace_text_btn: 'Trace text',
      clear_btn: 'Clear',
      empty_input: 'Provide the export file or paste the export first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ The critical path, delay contributors and SLA verdict appear here.',
      home: 'Home',
      running: 'Tracing…',
    },
  },
  zh: {
    translation: {
      title: '调度依赖延迟分析',
      subtitle:
        '产出为什么晚了？粘贴一轮调度的任务实例导出（JSON 或 CSV，' +
        '字段 name/start/end/deps）或指向文件 — 计算到目标任务的关键路径，' +
        '每一跳按"等依赖 vs 自身运行"归因。确定性分析，不连调度器。',
      file_label: '导出文件路径',
      file_ph: '任务实例导出 (.json/.csv)，如 examples/slatrace_demo/run.json',
      target_label: '目标任务（可选）',
      target_ph: '默认取最晚结束的任务',
      deadline_label: 'SLA 截止时间（可选）',
      deadline_ph: '如 2024-05-01 05:00:00',
      trace_btn: '分析文件',
      text_acc: '分析粘贴的导出',
      text_label: 'JSON / CSV 导出',
      text_ph: '[{"name":"a","start":"...","end":"...","deps":[]}, ...]',
      trace_text_btn: '分析文本',
      clear_btn: '清空',
      empty_input: '请先填写导出文件路径或粘贴导出内容。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 关键路径、延迟大户与 SLA 结论在此显示。',
      home: '首页',
      running: '分析中…',
    },
  },
}

export default initI18n(resources)
