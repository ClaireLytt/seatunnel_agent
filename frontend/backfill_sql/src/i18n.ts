import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Backfill SQL',
      subtitle:
        'How to backfill history safely? Describe the backfill in a JSON ' +
        'spec — target table, partition column, business date range, a ' +
        'source SELECT bounded by the {date} placeholder, write mode and ' +
        'dialect — and get one idempotent, partition-bounded statement ' +
        'block per date plus row-count pre-checks. The SQL is generated, ' +
        'never executed.',
      file_label: 'Spec file path',
      file_ph: 'Backfill spec (.json), e.g. examples/backfillsql_demo/spec.json',
      run_btn: 'Generate from file',
      text_acc: 'Generate from pasted spec',
      text_label: 'JSON backfill spec',
      text_ph:
        '{"table":"dws.sales","partition_col":"dt","start":"2024-05-01",' +
        '"end":"2024-05-03","mode":"overwrite","dialect":"hive",' +
        '"source":"SELECT ... FROM ods.orders WHERE dt = \'{date}\'"}',
      run_text_btn: 'Generate from text',
      clear_btn: 'Clear',
      empty_input: 'Provide the spec file or paste the spec first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ The pre-checks and per-date backfill statements appear here.',
      home: 'Home',
      running: 'Generating…',
    },
  },
  zh: {
    translation: {
      title: '回溯补数 SQL',
      subtitle:
        '历史数据怎么补才安全？用 JSON 规格描述补数 — 目标表、分区列、' +
        '业务日期区间、带 {date} 占位符的 source SELECT、写入模式与方言 — ' +
        '按日期生成幂等、带分区边界的补数语句块，附行数前置校验。' +
        'SQL 只生成，不执行。',
      file_label: '规格文件路径',
      file_ph: '补数规格 (.json)，如 examples/backfillsql_demo/spec.json',
      run_btn: '从文件生成',
      text_acc: '用粘贴的规格生成',
      text_label: 'JSON 补数规格',
      text_ph:
        '{"table":"dws.sales","partition_col":"dt","start":"2024-05-01",' +
        '"end":"2024-05-03","mode":"overwrite","dialect":"hive",' +
        '"source":"SELECT ... FROM ods.orders WHERE dt = \'{date}\'"}',
      run_text_btn: '用文本生成',
      clear_btn: '清空',
      empty_input: '请先填写规格文件路径或粘贴规格。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 前置校验与按日期的补数语句在此显示。',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
