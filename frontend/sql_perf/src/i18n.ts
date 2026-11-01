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
      before_acc: 'Compare against the pre-optimization plan',
      before_ph:
        '== Physical Plan ==  -- the EXPLAIN output BEFORE the change;\n' +
        'the report gains a resolved / introduced / remaining diff',
      rewrite_acc: 'LLM rewrite of the SQL',
      sql_ph: 'SELECT ... -- the original SQL behind this plan',
      llm_label: 'Draft the optimized SQL (needs an API key)',
      llm_needs_sql: 'Paste the original SQL first for the rewrite.',
      to_indexadvisor: 'Recommend indexes for this SQL',
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
      before_acc: '与优化前计划对比',
      before_ph:
        '== Physical Plan ==  -- 改动前的 EXPLAIN 输出；\n报告将追加已解决 / 新增 / 遗留对比节',
      rewrite_acc: 'LLM 改写 SQL',
      sql_ph: 'SELECT ... -- 该计划对应的原 SQL',
      llm_label: '生成优化 SQL 草案（需 API key）',
      llm_needs_sql: '请先粘贴原 SQL 再勾选改写。',
      to_indexadvisor: '用这条 SQL 推荐索引',
      home: '首页',
      running: '分析中…',
    },
  },
}

export default initI18n(resources)
