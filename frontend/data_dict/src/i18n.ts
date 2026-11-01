import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Data Dictionary',
      subtitle:
        'Paste the asset catalog (JSON list or CREATE TABLE DDL), ' +
        'optionally with a SQL workload — every column comes back with ' +
        'its inferred role (key/time/measure/flag/dimension), existing ' +
        'comment and filter/join/group usage counts; per-table comment ' +
        'coverage names the gaps the LLM can draft. No database ' +
        'connection.',
      catalog_label: 'Asset catalog (JSON or DDL)',
      catalog_ph: 'CREATE TABLE dwd.orders (order_id BIGINT COMMENT ...)',
      sql_label: 'SQL workload (optional)',
      sql_ph: 'SELECT ... FROM dwd.orders WHERE ... GROUP BY ...',
      run_btn: 'Generate',
      clear_btn: 'Clear',
      empty_input: 'Paste the catalog first.',
      report_ph: '▶ The dictionary skeleton appears here.',
      llm_label: 'LLM description drafts (needs an API key)',
      home: 'Home',
      running: 'Generating…',
    },
  },
  zh: {
    translation: {
      title: '数据字典生成',
      subtitle:
        '粘贴资产目录（JSON 清单或建表 DDL），可选再贴一份 SQL 负载 — ' +
        '逐列返回推断角色（键/时间/度量/标志/维度）、已有注释与' +
        '过滤/关联/分组使用频次；各表注释覆盖率点名缺口，LLM 可代笔。' +
        '不连数据库。',
      catalog_label: '资产目录（JSON 或 DDL）',
      catalog_ph: 'CREATE TABLE dwd.orders (order_id BIGINT COMMENT ...)',
      sql_label: 'SQL 负载（可选）',
      sql_ph: 'SELECT ... FROM dwd.orders WHERE ... GROUP BY ...',
      run_btn: '生成',
      clear_btn: '清空',
      empty_input: '请先粘贴资产目录。',
      report_ph: '▶ 字典骨架在此显示。',
      llm_label: 'LLM 业务描述草稿（需 API key）',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
