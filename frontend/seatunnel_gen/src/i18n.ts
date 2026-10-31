import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Job Draft',
      subtitle:
        'Nobody writes the first job.conf by hand. Paste the table DDL ' +
        'and name the source and sink connectors — the draft fills ' +
        'database, table and topic from the DDL, carries documented ' +
        'examples for the rest with every placeholder named, picks ' +
        'STREAMING for CDC sources, and leaves linted clean.',
      sql_label: 'CREATE TABLE DDL',
      sql_ph: 'CREATE TABLE db.t ( ... );',
      source_label: 'Source connector',
      source_ph: 'e.g. MySQL-CDC, Jdbc, Kafka',
      sink_label: 'Sink connector',
      sink_ph: 'e.g. Doris, Hive, ClickHouse',
      mode_label: 'Job mode (empty = auto)',
      mode_ph: 'BATCH / STREAMING',
      run_btn: 'Draft job',
      clear_btn: 'Clear',
      empty_input: 'Paste the DDL and name both connectors first.',
      report_ph: '▶ Parameters and job.conf appear here.',
      llm_label: 'LLM pre-run review (needs an API key)',
      home: 'Home',
      running: 'Drafting…',
    },
  },
  zh: {
    translation: {
      title: '作业配置生成',
      subtitle:
        '第一份 job.conf 没人愿意手写。粘贴表 DDL，填源/目标连接器 — ' +
        '库、表、topic 按 DDL 填充，其余必填参数带文档示例并点名待替换，' +
        'CDC 源自动 STREAMING，配置体检零错误出厂。',
      sql_label: 'CREATE TABLE DDL',
      sql_ph: 'CREATE TABLE db.t ( ... );',
      source_label: '源连接器',
      source_ph: '如 MySQL-CDC、Jdbc、Kafka',
      sink_label: '目标连接器',
      sink_ph: '如 Doris、Hive、ClickHouse',
      mode_label: '作业模式（留空自动）',
      mode_ph: 'BATCH / STREAMING',
      run_btn: '生成作业配置',
      clear_btn: '清空',
      empty_input: '请先粘贴 DDL 并填两个连接器。',
      report_ph: '▶ 参数清单与 job.conf 在此显示。',
      llm_label: 'LLM 运行前评审（需 API key）',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
