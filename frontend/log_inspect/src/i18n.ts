import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Batch Log Inspection',
      subtitle:
        'Exception clustering over a log directory — ERROR/WARN events ' +
        'are normalized and grouped by root cause, so a noisy directory ' +
        'collapses into Top-N distinct problems. Deterministic, nothing executed.',
      dir_label: 'Log directory',
      dir_ph: 'Directory containing *.log files (scanned recursively), e.g. examples/logs_demo',
      warn_label: 'Include WARN events',
      top_label: 'Top clusters',
      scan_btn: 'Inspect directory',
      text_acc: 'Inspect pasted log text',
      text_label: 'Log text',
      text_ph: 'Paste log lines / a stack trace…',
      scan_text_btn: 'Inspect text',
      clear_btn: 'Clear',
      empty_dir: '⚠️ Provide a log directory first.',
      empty_text: '⚠️ Paste some log text first.',
      bad_dir: '⚠️ Not a directory: ',
      advice_acc: 'LLM advice (optional)',
      advice_btn: 'Generate LLM advice',
      advice_none: 'No clusters to advise on — run a scan first.',
      advice_no_key: 'No API key configured.',
      report_ph: '▶ Clustered exceptions and the inspection report appear here.',
      home: 'Home',
      running: 'Inspecting…',
    },
  },
  zh: {
    translation: {
      title: '批量日志巡检',
      subtitle:
        '对日志目录做异常聚类 — ERROR/WARN 事件按根因归一化分组，' +
        '嘈杂的日志目录收敛成 Top-N 个不同的问题。确定性扫描，不执行任何操作。',
      dir_label: '日志目录',
      dir_ph: '包含 *.log 的目录（递归扫描），如 examples/logs_demo',
      warn_label: '包含 WARN 事件',
      top_label: 'Top 簇数',
      scan_btn: '巡检目录',
      text_acc: '巡检粘贴的日志',
      text_label: '日志文本',
      text_ph: '粘贴日志行 / 异常堆栈…',
      scan_text_btn: '巡检文本',
      clear_btn: '清空',
      empty_dir: '⚠️ 请先填写日志目录。',
      empty_text: '⚠️ 请先粘贴日志文本。',
      bad_dir: '⚠️ 不是有效目录: ',
      advice_acc: 'LLM 建议（可选）',
      advice_btn: '生成 LLM 建议',
      advice_none: '没有可分析的异常簇 — 请先执行巡检。',
      advice_no_key: '未配置 API key。',
      report_ph: '▶ 聚类结果与巡检报告在此显示。',
      home: '首页',
      running: '巡检中…',
    },
  },
}

export default initI18n(resources)
