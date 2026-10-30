import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/data_lineage/ui_impact.py). The legacy `title` markdown is
// split into title (heading, 💥 glyph moves next to the h1) + subtitle;
// result_ph drops the markdown *italics*. {var} placeholders become
// i18next {{var}}. Report/graph wording stays backend-rendered.
const resources = {
  en: {
    translation: {
      title: 'Change Impact Analysis',
      subtitle:
        'SQL diff × lineage: compare two SQL trees — or just paste ' +
        'the before/after SQL — and report the release blast ' +
        'radius: changed tables, downstream impact and severity ' +
        '(error / warn / info). No database connection, the SQL is ' +
        'never executed.',
      tab_dirs: 'Directories',
      tab_paste: 'Paste SQL',
      old_label: 'Old SQL directory',
      old_ph: 'SQL tree before the change, e.g. examples/impact_demo/old',
      new_label: 'New SQL directory',
      new_ph: 'SQL tree after the change, e.g. examples/impact_demo/new',
      old_sql_label: 'Old SQL',
      old_sql_ph: 'Paste the SQL before the change…',
      new_sql_label: 'New SQL',
      new_sql_ph: 'Paste the SQL after the change…',
      ctx_label: 'Context SQL directory (optional)',
      ctx_ph: 'Repo SQL tree; widens the blast radius to real consumers',
      dialect_label: 'SQL dialect',
      depth_label: 'Downstream depth',
      analyze_btn: 'Analyze change impact',
      analyze_sql_btn: 'Analyze pasted SQL',
      result_ph: 'Fill both sides and click Analyze.',
      need_dirs: 'Provide both the old and the new SQL directory.',
      need_sql: 'Paste both the old and the new SQL.',
      bad_dir: '❌ Not a directory: `{{d}}`',
      fail: '❌ **Analysis failed**: {{exc}}',
      running: 'Analyzing…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '变更影响分析',
      subtitle:
        'SQL 变更 × 血缘：对比两份 SQL 目录，或直接粘贴改动前后的' +
        '两段 SQL，输出上线影响面——变更了哪些表、下游波及多深、' +
        '按严重度分级（error / warn / info）。不连接数据库，' +
        '不执行 SQL。',
      tab_dirs: '目录模式',
      tab_paste: '粘贴 SQL',
      old_label: '旧 SQL 目录',
      old_ph: '变更前的 SQL 目录，如 examples/impact_demo/old',
      new_label: '新 SQL 目录',
      new_ph: '变更后的 SQL 目录，如 examples/impact_demo/new',
      old_sql_label: '旧 SQL',
      old_sql_ph: '粘贴变更前的 SQL…',
      new_sql_label: '新 SQL',
      new_sql_ph: '粘贴变更后的 SQL…',
      ctx_label: '上下文 SQL 目录（可选）',
      ctx_ph: '仓库 SQL 目录；填写后下游波及按全仓血缘计算',
      dialect_label: 'SQL 方言',
      depth_label: '下游深度',
      analyze_btn: '变更影响分析',
      analyze_sql_btn: '分析粘贴的 SQL',
      result_ph: '填写两侧内容后点击分析。',
      need_dirs: '请同时填写旧、新两个 SQL 目录。',
      need_sql: '请同时粘贴旧、新两段 SQL。',
      bad_dir: '❌ 不是有效目录: `{{d}}`',
      fail: '❌ **分析失败**: {{exc}}',
      running: '分析中…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
