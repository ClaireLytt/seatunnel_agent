import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Layer Check',
      subtitle:
        'Does the pipeline respect the warehouse layering? Paste the SQL ' +
        'scripts — tables get layers from their name prefixes (ods/stg, ' +
        'dwd/dim, dws/dwm, ads/rpt/app, or your own map) and every ' +
        'lineage edge is judged: layer skips, reverse dependencies, ' +
        'same-layer chaining and unknown-layer names, each with a ' +
        'refactoring prescription. No database connection.',
      sql_label: 'Pipeline SQL scripts',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      layers_label: 'Custom layer map (optional JSON)',
      layers_ph: '{"ods": 0, "dwd": 1, "dws": 2, "ads": 3}',
      run_btn: 'Check',
      clear_btn: 'Clear',
      empty_input: 'Paste the SQL first.',
      report_ph: '▶ Layering violations with prescriptions appear here.',
      llm_label: 'LLM layering note (needs an API key)',
      home: 'Home',
      running: 'Checking…',
    },
  },
  zh: {
    translation: {
      title: '数仓分层体检',
      subtitle:
        '流水线守不守分层？粘贴 SQL 脚本 — 表按命名前缀定层（ods/stg、' +
        'dwd/dim、dws/dwm、ads/rpt/app，或自定义分层表），逐条血缘边' +
        '判定：跨层引用、反向依赖、同层叠加与未知分层，每条附整改处方。' +
        '不连数据库。',
      sql_label: '流水线 SQL 脚本',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      layers_label: '自定义分层表（可选 JSON）',
      layers_ph: '{"ods": 0, "dwd": 1, "dws": 2, "ads": 3}',
      run_btn: '体检',
      clear_btn: '清空',
      empty_input: '请先粘贴 SQL。',
      report_ph: '▶ 分层违规与处方在此显示。',
      llm_label: 'LLM 整改通报（需 API key）',
      home: '首页',
      running: '体检中…',
    },
  },
}

export default initI18n(resources)
