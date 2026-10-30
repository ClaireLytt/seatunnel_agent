import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Plan Analyzer',
      subtitle:
        'What did the engine actually plan? Paste the output of EXPLAIN ' +
        'or EXPLAIN FORMATTED (Spark / Hive) — join types, shuffle count ' +
        'and each scan’s partition pruning and filter pushdown are ' +
        'read out, with severity-ranked findings and prescriptions. ' +
        'Deterministic, no engine connection.',
      file_label: 'Plan file path',
      file_ph: 'EXPLAIN output (.txt), e.g. examples/sqlperf_demo/plan.txt',
      run_btn: 'Analyze file',
      text_acc: 'Analyze pasted plan',
      text_label: 'EXPLAIN output',
      text_ph:
        '== Physical Plan ==\n+- Exchange hashpartitioning(...)\n   +- FileScan parquet db.t[...] PartitionFilters: [...], PushedFilters: [...]',
      run_text_btn: 'Analyze text',
      clear_btn: 'Clear',
      empty_input: 'Provide the plan file or paste the EXPLAIN output first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ Findings, joins, shuffles and per-scan pruning appear here.',
      home: 'Home',
      running: 'Analyzing…',
    },
  },
  zh: {
    translation: {
      title: '执行计划分析',
      subtitle:
        '引擎到底打算怎么跑？粘贴 EXPLAIN / EXPLAIN FORMATTED 的输出' +
        '（Spark / Hive）— 解析 join 类型、shuffle 数量、各表扫描的分区' +
        '裁剪与谓词下推，按级别给出发现与处方。确定性解读，不连引擎。',
      file_label: '计划文件路径',
      file_ph: 'EXPLAIN 输出 (.txt)，如 examples/sqlperf_demo/plan.txt',
      run_btn: '分析文件',
      text_acc: '用粘贴的计划分析',
      text_label: 'EXPLAIN 输出',
      text_ph:
        '== Physical Plan ==\n+- Exchange hashpartitioning(...)\n   +- FileScan parquet db.t[...] PartitionFilters: [...], PushedFilters: [...]',
      run_text_btn: '用文本分析',
      clear_btn: '清空',
      empty_input: '请先填写计划文件路径或粘贴 EXPLAIN 输出。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 发现、join、shuffle 与各表裁剪情况在此显示。',
      home: '首页',
      running: '分析中…',
    },
  },
}

export default initI18n(resources)
