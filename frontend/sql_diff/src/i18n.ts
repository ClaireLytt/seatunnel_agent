import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'SQL Diff',
      subtitle:
        'git diff shows a reformatted query as a wall of changes and a ' +
        're-aliased join as nothing. Paste the two versions — ' +
        'statements pair by write target and only differences that ' +
        'change meaning show up, graded: dropped columns and INSERT ' +
        'flips as breaking, filter and aggregation shifts as risk.',
      old_label: 'Old SQL',
      new_label: 'New SQL',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      run_btn: 'Compare',
      clear_btn: 'Clear',
      empty_input: 'Paste both versions first.',
      report_ph: '▶ Graded semantic differences appear here.',
      llm_label: 'LLM change review (needs an API key)',
      home: 'Home',
      running: 'Comparing…',
    },
  },
  zh: {
    translation: {
      title: 'SQL 语义对比',
      subtitle:
        'git diff 把重排格式当成满屏变更，把换别名的 join 当成没变。' +
        '粘贴两版 SQL — 语句按写入目标配对，只报改变语义的差异并分级：' +
        '删列与 INSERT 翻转记破坏，过滤与聚合口径漂移记风险。',
      old_label: '旧版 SQL',
      new_label: '新版 SQL',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      run_btn: '开始对比',
      clear_btn: '清空',
      empty_input: '请先粘贴两版 SQL。',
      report_ph: '▶ 分级语义差异在此显示。',
      llm_label: 'LLM 变更评审（需 API key）',
      home: '首页',
      running: '对比中…',
    },
  },
}

export default initI18n(resources)
