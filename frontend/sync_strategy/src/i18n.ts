import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Sync Strategy',
      subtitle:
        'Full, incremental or CDC? Point at the per-table characteristics ' +
        'inventory (JSON, CSV or CREATE TABLE DDL — rows, daily churn, ' +
        'update timestamp, primary key, deletes, binlog, latency) and each ' +
        'table gets a recommended strategy with the rule trace and the ' +
        'residual risks. Deterministic, no database connection.',
      file_label: 'Inventory file path',
      file_ph: 'Table profile (.json/.csv), e.g. examples/syncstrategy_demo/tables.json',
      llm_label: 'LLM rollout narrative (needs an API key)',
      run_btn: 'Recommend from file',
      text_acc: 'Recommend from pasted inventory',
      text_label: 'JSON / CSV table characteristics',
      text_ph:
        '[{"table":"ods.orders","rows":50000000,"daily_change_rows":800000,' +
        '"has_update_ts":true,"has_pk":true,"cdc_available":true,' +
        '"latency":"minutes"}, ...]',
      run_text_btn: 'Recommend from text',
      clear_btn: 'Clear',
      empty_input: 'Provide the inventory file or paste the table profiles first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ The per-table strategy, reasons and risks appear here.',
      home: 'Home',
      running: 'Recommending…',
    },
  },
  zh: {
    translation: {
      title: '增量同步策略',
      subtitle:
        '全量、增量还是 CDC？指向按表的特征清单（JSON、CSV 或 CREATE TABLE DDL — 行数、' +
        '日变更量、更新时间列、主键、物理删除、binlog 可用性、时延要求），' +
        '逐表给出推荐策略、规则依据与剩余风险。确定性规则，不连数据库。',
      file_label: '清单文件路径',
      file_ph: '表特征清单 (.json/.csv)，如 examples/syncstrategy_demo/tables.json',
      llm_label: 'LLM 落地推进方案（需 API key）',
      run_btn: '从文件推荐',
      text_acc: '用粘贴的清单推荐',
      text_label: 'JSON / CSV 表特征',
      text_ph:
        '[{"table":"ods.orders","rows":50000000,"daily_change_rows":800000,' +
        '"has_update_ts":true,"has_pk":true,"cdc_available":true,' +
        '"latency":"minutes"}, ...]',
      run_text_btn: '用文本推荐',
      clear_btn: '清空',
      empty_input: '请先填写清单文件路径或粘贴表特征。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 逐表的策略、理由与风险在此显示。',
      home: '首页',
      running: '推荐中…',
    },
  },
}

export default initI18n(resources)
