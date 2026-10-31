import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'DDL Migration',
      subtitle:
        'The diff is not the deliverable — the script is. Paste the old ' +
        'and new CREATE TABLE snapshots: widenings, added columns, ' +
        'renames and new tables come back as runnable statements, while ' +
        'drops, narrowings and partition changes stay commented with a ' +
        'review note.',
      old_label: 'Old DDL snapshot',
      new_label: 'New DDL snapshot',
      ddl_ph: 'CREATE TABLE ods.t ( ... );',
      dialect_label: 'Dialect (hive / mysql)',
      run_btn: 'Build migration',
      clear_btn: 'Clear',
      empty_input: 'Paste both DDL snapshots first.',
      report_ph: '▶ Steps and the migration script appear here.',
      llm_label: 'LLM rollout advice (needs an API key)',
      home: 'Home',
      running: 'Building…',
    },
  },
  zh: {
    translation: {
      title: 'DDL 迁移脚本',
      subtitle:
        '差异报告不是交付物，脚本才是。粘贴新旧两版 CREATE TABLE 快照：' +
        '拓宽、加列、改名、新建表直接给可执行语句；删表删列、类型收窄、' +
        '分区变更保持注释并附评审提示，防止误执行。',
      old_label: '旧版 DDL 快照',
      new_label: '新版 DDL 快照',
      ddl_ph: 'CREATE TABLE ods.t ( ... );',
      dialect_label: '方言（hive / mysql）',
      run_btn: '生成迁移脚本',
      clear_btn: '清空',
      empty_input: '请先粘贴两版 DDL 快照。',
      report_ph: '▶ 迁移步骤与脚本在此显示。',
      llm_label: 'LLM 上线建议（需 API key）',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
