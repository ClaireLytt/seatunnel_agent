import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Offboarding Plan',
      subtitle:
        'Retiring a table without paging anyone takes staging. Paste ' +
        'the pipeline SQL and the table — live downstream consumers ' +
        'block the plan and are named for migration; otherwise announce, ' +
        'freeze, archive and a commented DROP come back in order.',
      sql_label: 'Pipeline SQL scripts',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      table_label: 'Table to retire',
      table_ph: 'e.g. ads.final_report',
      grace_label: 'Grace window (days)',
      run_btn: 'Stage retirement',
      clear_btn: 'Clear',
      empty_input: 'Paste the SQL and name the table first.',
      report_ph: '▶ Staged steps and templates appear here.',
      llm_label: 'LLM retirement notice (needs an API key)',
      home: 'Home',
      running: 'Staging…',
    },
  },
  zh: {
    translation: {
      title: '下线方案',
      subtitle:
        '下线一张表而不惊动任何人，靠的是分阶段。粘贴流水线 SQL 和表名 ' +
        '— 下游还有人读就判受阻并点名先迁移；否则按公示、冻结、归档、' +
        '注释版 DROP 的顺序给出步骤。',
      sql_label: '流水线 SQL 脚本',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      table_label: '要下线的表',
      table_ph: '如 ads.final_report',
      grace_label: '公示期（天）',
      run_btn: '生成下线方案',
      clear_btn: '清空',
      empty_input: '请先粘贴 SQL 并填表名。',
      report_ph: '▶ 分阶段步骤与模板在此显示。',
      llm_label: 'LLM 下线通告（需 API key）',
      home: '首页',
      running: '编排中…',
    },
  },
}

export default initI18n(resources)
