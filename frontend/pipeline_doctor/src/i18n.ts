import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Pipeline Failure Diagnosis',
      subtitle:
        'Diagnose a failed Spark/Hive/SeaTunnel run from its logs — the ' +
        'engine is detected, exception clusters are matched against a ' +
        'failure-signature knowledge base, and each hit comes with the ' +
        'likely cause and the fix. Deterministic, nothing executed.',
      dir_label: 'Run log directory',
      dir_ph: 'Directory with the run logs (scanned recursively), e.g. examples/pipedoctor_demo',
      top_label: 'Max findings',
      diagnose_btn: 'Diagnose directory',
      text_acc: 'Diagnose pasted log text',
      text_label: 'Log text',
      text_ph: 'Paste the failed run log / stack trace…',
      diagnose_text_btn: 'Diagnose text',
      clear_btn: 'Clear',
      empty_dir: 'Provide a log directory first.',
      empty_text: 'Paste some log text first.',
      bad_dir: 'Not a directory: ',
      advice_acc: 'LLM advice (optional)',
      advice_btn: 'Generate LLM advice',
      advice_none: 'Nothing to advise on — run a diagnosis first.',
      report_ph: '▶ The diagnosis — primary suspect, causes and fixes — appears here.',
      home: 'Home',
      running: 'Diagnosing…',
    },
  },
  zh: {
    translation: {
      title: 'Pipeline 故障诊断',
      subtitle:
        '分析失败的 Spark/Hive/SeaTunnel 运行日志 — 识别引擎、' +
        '将异常簇与故障签名知识库匹配，每个命中给出可能原因与修复方案。' +
        '确定性诊断，不执行任何操作。',
      dir_label: '运行日志目录',
      dir_ph: '包含运行日志的目录（递归扫描），如 examples/pipedoctor_demo',
      top_label: '最多命中项',
      diagnose_btn: '诊断目录',
      text_acc: '诊断粘贴的日志',
      text_label: '日志文本',
      text_ph: '粘贴失败运行的日志 / 异常堆栈…',
      diagnose_text_btn: '诊断文本',
      clear_btn: '清空',
      empty_dir: '请先填写日志目录。',
      empty_text: '请先粘贴日志文本。',
      bad_dir: '不是有效目录: ',
      advice_acc: 'LLM 建议（可选）',
      advice_btn: '生成 LLM 建议',
      advice_none: '没有可分析的结果 — 请先执行诊断。',
      report_ph: '▶ 诊断结果 — 首要嫌疑、根因与修复方案在此显示。',
      home: '首页',
      running: '诊断中…',
    },
  },
}

export default initI18n(resources)
