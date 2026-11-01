import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'DAG Draft',
      subtitle:
        'Nobody wants to hand-wire the scheduler file. Paste the ' +
        'pipeline SQL — every write target becomes a task, dependency ' +
        'edges come from the lineage, external upstreams are flagged ' +
        'where sensors belong, and the dag.py parses clean. Replace the ' +
        'RUN placeholders and deploy.',
      sql_label: 'Pipeline SQL (INSERT / CREATE statements)',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      dagid_label: 'dag_id',
      schedule_label: 'Schedule (cron)',
      run_btn: 'Draft DAG',
      clear_btn: 'Clear',
      empty_input: 'Paste the pipeline SQL first.',
      report_ph: '▶ Tasks, edges and dag.py appear here.',
      llm_label: 'LLM pre-deploy review (needs an API key)',
      home: 'Home',
      running: 'Drafting…',
    },
  },
  zh: {
    translation: {
      title: '调度文件生成',
      subtitle:
        '没人愿意手工接线调度文件。粘贴流水线 SQL — 每个写入目标生成' +
        '一个任务，依赖边来自血缘，脚本外上游点名该挂 sensor 的位置，' +
        'dag.py 解析零错误。替换 RUN 占位符即可部署。',
      sql_label: '流水线 SQL（INSERT / CREATE 语句）',
      sql_ph: 'INSERT INTO dws.t SELECT ... FROM dwd.s ...;',
      dagid_label: 'dag_id',
      schedule_label: '调度（cron）',
      run_btn: '生成 DAG',
      clear_btn: '清空',
      empty_input: '请先粘贴流水线 SQL。',
      report_ph: '▶ 任务、依赖与 dag.py 在此显示。',
      llm_label: 'LLM 部署前评审（需 API key）',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
