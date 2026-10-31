import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Index Advisor',
      subtitle:
        'Which columns deserve the partition, the buckets and the index? ' +
        'Point at the query workload (a SQL directory or pasted ' +
        'statements), optionally with the CREATE TABLE DDL — per-column ' +
        'equality / range / join / GROUP BY hits are counted and each ' +
        'table gets its picks with hit counts and DDL fragments. ' +
        'Deterministic, no database connection.',
      dir_label: 'Workload SQL directory',
      dir_ph: 'recursive *.sql, e.g. examples/indexadvisor_demo',
      ddl_label: 'Table DDL (optional)',
      ddl_ph: 'CREATE TABLE ... — types make date-like detection precise',
      run_btn: 'Recommend from directory',
      text_acc: 'Recommend from pasted SQL',
      text_label: 'Multi-statement SQL workload',
      text_ph: 'SELECT ... FROM ods.orders o JOIN ods.users u ON ... WHERE o.dt = ...;',
      run_text_btn: 'Recommend from text',
      clear_btn: 'Clear',
      empty_input: 'Provide the SQL directory or paste the workload first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ Per-table partition / bucketing / index picks appear here.',
      to_sqlcost: 'Verify the saving on the cost page',
      home: 'Home',
      running: 'Recommending…',
    },
  },
  zh: {
    translation: {
      title: '索引分区推荐',
      subtitle:
        '哪些列值得做分区、分桶和索引？指向查询工作负载（SQL 目录或粘贴' +
        '多条语句），可选附建表 DDL — 统计每列的等值/范围/join/group 频次，' +
        '逐表给出推荐、命中次数与 DDL 片段。确定性计数，不连数据库。',
      dir_label: '工作负载 SQL 目录',
      dir_ph: '递归 *.sql，如 examples/indexadvisor_demo',
      ddl_label: '表 DDL（可选）',
      ddl_ph: 'CREATE TABLE ... — 有类型信息时时间列判断更准',
      run_btn: '从目录推荐',
      text_acc: '用粘贴的 SQL 推荐',
      text_label: '多条 SQL 工作负载',
      text_ph: 'SELECT ... FROM ods.orders o JOIN ods.users u ON ... WHERE o.dt = ...;',
      run_text_btn: '用文本推荐',
      clear_btn: '清空',
      empty_input: '请先填写 SQL 目录或粘贴工作负载。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 逐表的分区 / 分桶 / 索引推荐在此显示。',
      to_sqlcost: '到成本页验证能省多少',
      home: '首页',
      running: '推荐中…',
    },
  },
}

export default initI18n(resources)
