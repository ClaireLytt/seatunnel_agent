import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Cost Estimator',
      subtitle:
        'How much will this query cost before you run it? Paste the SQL ' +
        'and point at the table stats inventory (rows / bytes / ' +
        'partitions) — scan with pruning discounts, join and aggregation ' +
        'shuffles, peak memory, core-seconds and a wall-clock band come ' +
        'back as a cost card with every assumption stated. Deterministic, ' +
        'no database connection.',
      sql_label: 'SQL statement',
      sql_ph: 'SELECT ... FROM ods.orders o JOIN ods.users u ON ... WHERE o.dt = ...',
      stats_label: 'Stats inventory file',
      stats_ph: 'rows/bytes/partitions (.json/.csv), e.g. examples/sqlcost_demo/stats.json',
      run_btn: 'Estimate',
      stats_acc: 'Paste the stats inline',
      stats_text_label: 'JSON / CSV table stats',
      stats_text_ph:
        '[{"table":"ods.orders","rows":500000000,"bytes":107374182400,' +
        '"partitions":365,"partition_col":"dt","columns":20}, ...]',
      clear_btn: 'Clear',
      empty_input: 'Provide the SQL and the stats first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ The cost card (scan, shuffle, memory, time) appears here.',
      assume_label: 'What-if partitioning (optional)',
      assume_ph: 'table:col[:N], e.g. ods.users:user_id:10',
      home: 'Home',
      running: 'Estimating…',
    },
  },
  zh: {
    translation: {
      title: '资源消耗预测',
      subtitle:
        '这条查询跑之前要花多少资源？粘贴 SQL 并指向表统计清单' +
        '（行数/字节/分区数）— 扫描量（含裁剪折扣）、join 与聚合的 ' +
        'shuffle、内存峰值、核·秒与耗时区间以代价卡返回，所有假设随结果' +
        '列出。确定性估算，不连数据库。',
      sql_label: 'SQL 语句',
      sql_ph: 'SELECT ... FROM ods.orders o JOIN ods.users u ON ... WHERE o.dt = ...',
      stats_label: '统计清单文件',
      stats_ph: 'rows/bytes/partitions (.json/.csv)，如 examples/sqlcost_demo/stats.json',
      run_btn: '估算',
      stats_acc: '粘贴统计清单',
      stats_text_label: 'JSON / CSV 表统计',
      stats_text_ph:
        '[{"table":"ods.orders","rows":500000000,"bytes":107374182400,' +
        '"partitions":365,"partition_col":"dt","columns":20}, ...]',
      clear_btn: '清空',
      empty_input: '请先填写 SQL 与统计清单。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 代价卡（扫描、shuffle、内存、耗时）在此显示。',
      assume_label: 'What-if 假设分区（可选）',
      assume_ph: '表:列[:分区数]，如 ods.users:user_id:10',
      home: '首页',
      running: '估算中…',
    },
  },
}

export default initI18n(resources)
