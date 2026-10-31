import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Model Review',
      subtitle:
        'Does the star schema actually hold? Paste the warehouse DDL — ' +
        'prefixes decide the roles (dim / dwd·dws facts / ods·stg raw), ' +
        'then keyless dimensions, unpartitioned facts, attributes ' +
        'leaked into or copied across facts, measure-less aggregates ' +
        'and over-wide tables come back graded.',
      sql_label: 'CREATE TABLE DDL',
      sql_ph: 'CREATE TABLE dim.users ( ... );',
      wide_label: 'Wide-table threshold (columns)',
      run_btn: 'Review model',
      clear_btn: 'Clear',
      empty_input: 'Paste the CREATE TABLE DDL first.',
      report_ph: '▶ Graded star-schema findings appear here.',
      llm_label: 'LLM refactoring advice (needs an API key)',
      home: 'Home',
      running: 'Reviewing…',
    },
  },
  zh: {
    translation: {
      title: '建模体检',
      subtitle:
        '星型结构真的成立吗？粘贴数仓 DDL — 前缀决定角色（dim 维表 / ' +
        'dwd·dws 事实 / ods·stg 原始），维表缺主键、事实表缺分区缺外键、' +
        '维度属性混入或跨表复制、汇总表无度量、宽表，逐项分级给出。',
      sql_label: 'CREATE TABLE DDL',
      sql_ph: 'CREATE TABLE dim.users ( ... );',
      wide_label: '宽表阈值（列数）',
      run_btn: '开始体检',
      clear_btn: '清空',
      empty_input: '请先粘贴 CREATE TABLE DDL。',
      report_ph: '▶ 星型结构分级发现在此显示。',
      llm_label: 'LLM 改造建议（需 API key）',
      home: '首页',
      running: '体检中…',
    },
  },
}

export default initI18n(resources)
