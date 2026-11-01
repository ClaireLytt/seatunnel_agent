import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Asset Search',
      subtitle:
        'Which table answers the business need? Paste the asset catalog ' +
        '(a JSON list of tables with comments and columns, or CREATE ' +
        'TABLE DDL) and ask in plain language — hits come back weighted ' +
        'by table name, comments and columns, with the matched columns ' +
        'and hit locations shown, so the ranking explains itself. No ' +
        'database connection.',
      catalog_label: 'Asset catalog (JSON or DDL)',
      catalog_ph: '[{"table":"dws.orders_daily","comment":"...","columns":[...]}]',
      query_label: 'Business need',
      query_ph: 'e.g. 按日的订单金额汇总 / daily order amount',
      run_btn: 'Search',
      clear_btn: 'Clear',
      empty_input: 'Paste the catalog and type the need first.',
      report_ph: '▶ Explainable hits appear here.',
      llm_label: 'LLM pick-and-explain (needs an API key)',
      home: 'Home',
      running: 'Searching…',
    },
  },
  zh: {
    translation: {
      title: '数据资产搜索',
      subtitle:
        '业务需求该用哪张表？粘贴资产目录（带注释与列的 JSON 清单，或' +
        '建表 DDL），用自然语言提问 — 命中按表名/注释/列加权返回，' +
        '附命中列与命中位置，排序自己解释自己。不连数据库。',
      catalog_label: '资产目录（JSON 或 DDL）',
      catalog_ph: '[{"table":"dws.orders_daily","comment":"...","columns":[...]}]',
      query_label: '业务需求',
      query_ph: '如 按日的订单金额汇总',
      run_btn: '搜索',
      clear_btn: '清空',
      empty_input: '请先粘贴目录并填写需求。',
      report_ph: '▶ 可解释的命中排行在此显示。',
      llm_label: 'LLM 选表推荐（需 API key）',
      home: '首页',
      running: '搜索中…',
    },
  },
}

export default initI18n(resources)
