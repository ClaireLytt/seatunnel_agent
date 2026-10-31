import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Rollback Plan',
      subtitle:
        'A table loaded bad data — how do we back it out? Paste the ' +
        'pipeline SQL, name the bad table and partitions, pick the ' +
        'restore mode — the plan restores the table first, re-runs the ' +
        'downstream in topological levels (parallel inside a level) and ' +
        'verifies every touched table. No scheduler connection.',
      sql_label: 'Pipeline SQL scripts',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      table_label: 'Bad table',
      table_ph: 'e.g. dwd.orders',
      parts_label: 'Bad partitions (comma-separated, optional)',
      parts_ph: 'e.g. dt=2026-10-30',
      mode_label: 'Restore mode (snapshot / rerun / overwrite)',
      snapshot_label: 'Snapshot table (mode=snapshot)',
      snapshot_ph: 'e.g. snap_dwd_orders_20261030',
      run_btn: 'Plan rollback',
      clear_btn: 'Clear',
      empty_input: 'Paste the SQL and name the bad table first.',
      report_ph: '▶ Leveled restore and re-run steps appear here.',
      llm_label: 'LLM incident update (needs an API key)',
      home: 'Home',
      running: 'Planning…',
    },
  },
  zh: {
    translation: {
      title: '回滚编排',
      subtitle:
        '表写进了坏数据 — 怎么退？粘贴流水线 SQL，填坏表与坏分区，选' +
        '恢复方式 — 方案先恢复坏表，再按拓扑分层重跑下游（层内可并行），' +
        '每张涉及表附验证 SQL。不连调度器。',
      sql_label: '流水线 SQL 脚本',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      table_label: '写坏的表',
      table_ph: '如 dwd.orders',
      parts_label: '坏分区（逗号分隔，可选）',
      parts_ph: '如 dt=2026-10-30',
      mode_label: '恢复方式（snapshot / rerun / overwrite）',
      snapshot_label: '快照表（mode=snapshot 时）',
      snapshot_ph: '如 snap_dwd_orders_20261030',
      run_btn: '生成回滚方案',
      clear_btn: '清空',
      empty_input: '请先粘贴 SQL 并填坏表。',
      report_ph: '▶ 分层恢复与重跑步骤在此显示。',
      llm_label: 'LLM 事故进展通报（需 API key）',
      home: '首页',
      running: '编排中…',
    },
  },
}

export default initI18n(resources)
