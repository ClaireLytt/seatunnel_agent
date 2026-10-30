import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Migration Assessor',
      subtitle:
        'How big is the move to SeaTunnel / Spark / Flink? Point at the ' +
        'legacy scripts directory (.sql/.hql/.sh/.py, recursive) — each ' +
        'job gets a target engine, an S/M/L effort size from a ' +
        'transparent score, and the list of constructs that will not ' +
        'migrate mechanically. Static analysis only, nothing is executed.',
      dir_label: 'Scripts directory',
      dir_ph: 'e.g. examples/pipemigrate_demo',
      run_btn: 'Assess directory',
      text_acc: 'Assess one pasted script',
      text_label: 'Script content (SQL / shell / Python)',
      text_ph: 'INSERT OVERWRITE TABLE dws.sales SELECT ... FROM ods.orders ...;',
      run_text_btn: 'Assess script',
      clear_btn: 'Clear',
      empty_input: 'Provide the scripts directory or paste a script first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ Per-job target engine, effort size and risks appear here.',
      home: 'Home',
      running: 'Assessing…',
    },
  },
  zh: {
    translation: {
      title: 'Pipeline 迁移评估',
      subtitle:
        '迁到 SeaTunnel / Spark / Flink 要多大代价？指向旧脚本目录' +
        '（.sql/.hql/.sh/.py，递归扫描）— 逐任务给出目标引擎、按透明打分' +
        '得出的 S/M/L 工作量，以及无法机械翻译的语法清单。只做静态分析，' +
        '不执行任何内容。',
      dir_label: '脚本目录',
      dir_ph: '如 examples/pipemigrate_demo',
      run_btn: '评估目录',
      text_acc: '评估粘贴的单个脚本',
      text_label: '脚本内容（SQL / shell / Python）',
      text_ph: 'INSERT OVERWRITE TABLE dws.sales SELECT ... FROM ods.orders ...;',
      run_text_btn: '评估脚本',
      clear_btn: '清空',
      empty_input: '请先填写脚本目录或粘贴脚本。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 逐任务的目标引擎、工作量与风险在此显示。',
      home: '首页',
      running: '评估中…',
    },
  },
}

export default initI18n(resources)
