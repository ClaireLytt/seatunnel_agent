import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Backfill Planner',
      subtitle:
        'What needs re-running, for which dates, in which order? Point at ' +
        'the per-table update-event inventory (JSON or CSV) — missing ' +
        'partition slots are found on the cadence grid, cascaded through ' +
        'the lineage built from your SQL directory, and ordered into ' +
        'topological batches. Deterministic, no database or scheduler ' +
        'connection.',
      file_label: 'Inventory file path',
      file_ph: 'Update events (.json/.csv), e.g. examples/backfill_demo/updates.json',
      rules_label: 'Rules file (optional)',
      rules_ph: 'e.g. examples/backfill_demo/rules.json',
      sql_label: 'Lineage SQL directory (optional)',
      sql_ph: 'e.g. examples/backfill_demo/sql',
      cmd_label: 'Command template (optional)',
      cmd_ph: 'e.g. airflow tasks run {table} {date}',
      plan_btn: 'Plan file',
      text_acc: 'Plan pasted inventory',
      text_label: 'JSON / CSV update events',
      text_ph: '[{"table":"ods.orders","updated":"2024-05-01 02:40:00"}, ...]',
      plan_text_btn: 'Plan text',
      clear_btn: 'Clear',
      empty_input: 'Provide the inventory file or paste the events first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ The batches, tables and dates to re-run appear here.',
      to_backfillsql: 'Generate backfill SQL specs from this plan',
      home: 'Home',
      running: 'Planning…',
    },
  },
  zh: {
    translation: {
      title: '分区补数计划',
      subtitle:
        '该补哪些表、哪些日期、按什么顺序跑？指向按表的更新事件清单' +
        '（JSON 或 CSV）— 按节奏网格找出缺失分区，沿 SQL 目录构建的血缘' +
        '级联到下游，并给出拓扑批次顺序。确定性计划，不连数据库，不连调度器。',
      file_label: '清单文件路径',
      file_ph: '更新事件 (.json/.csv)，如 examples/backfill_demo/updates.json',
      rules_label: '规则文件（可选）',
      rules_ph: '如 examples/backfill_demo/rules.json',
      sql_label: '血缘 SQL 目录（可选）',
      sql_ph: '如 examples/backfill_demo/sql',
      cmd_label: '命令模板（可选）',
      cmd_ph: '如 airflow tasks run {table} {date}',
      plan_btn: '生成计划',
      text_acc: '用粘贴的清单生成计划',
      text_label: 'JSON / CSV 更新事件',
      text_ph: '[{"table":"ods.orders","updated":"2024-05-01 02:40:00"}, ...]',
      plan_text_btn: '用文本生成',
      clear_btn: '清空',
      empty_input: '请先填写清单文件路径或粘贴更新事件。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 需要补数/重跑的批次、表与日期在此显示。',
      to_backfillsql: '用此计划生成补数 SQL 规格',
      home: '首页',
      running: '规划中…',
    },
  },
}

export default initI18n(resources)
