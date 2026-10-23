import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Environment Doctor',
      subtitle:
        'Describe what\'s wrong — the agent inspects ports, packages, ' +
        'LLM config and log tails (all read-only) and prescribes the ' +
        'fix commands for YOU to run. Without an API key it prints a ' +
        'full deterministic check-up instead.',
      c_label: 'Symptom',
      c_ph: 'e.g. seatunnel-agent ui exits immediately on port 7860',
      run_btn: 'Diagnose',
      checkup_btn: 'Full check-up (no LLM)',
      clear_btn: 'Clear',
      report_ph: '▶ Diagnosis and prescribed commands appear here.',
      empty: '⚠️ Describe the symptom first.',
      home: 'Home',
      running: 'Diagnosing…',
    },
  },
  zh: {
    translation: {
      title: '环境医生',
      subtitle:
        '描述症状（「UI 起不来」「LLM 调用超时」）— agent 自己检查端口、' +
        '依赖、LLM 配置与日志尾部（全只读），给出修复命令由你执行。' +
        '未配置 API key 时输出确定性全量体检报告。',
      c_label: '症状描述',
      c_ph: '例如：seatunnel-agent ui 在 7860 端口启动后立刻退出',
      run_btn: '诊断',
      checkup_btn: '全量体检（不调 LLM）',
      clear_btn: '清空',
      report_ph: '▶ 诊断结论与修复命令在此显示。',
      empty: '⚠️ 请先描述症状。',
      home: '首页',
      running: '诊断中…',
    },
  },
}

export default initI18n(resources)
