import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Governance Overview',
      subtitle:
        'The governance agents keep a JSONL history of every CLI and API ' +
        'run. This page reads those histories: latest posture and trend ' +
        'per agent, one glance.',
      hygiene: 'Warehouse Hygiene',
      metaquality: 'Metadata Quality',
      contract: 'Data Contract',
      grants: 'Grant Surface',
      ddlguard: 'Migration Guard',
      latest: 'latest',
      runs: 'runs',
      trend: 'total findings, oldest to newest',
      empty: 'No runs recorded yet — run the agent once from its page or CLI.',
      open: 'Open',
    },
  },
  zh: {
    translation: {
      title: '治理总览',
      subtitle:
        '治理 agent 的每次 CLI/API 运行都会落一条 JSONL 历史。' +
        '本页读这些历史:每个 agent 的最新状态与趋势,一眼看完。',
      hygiene: '数仓卫生',
      metaquality: '元数据质量',
      contract: '数据契约',
      grants: '权限面',
      ddlguard: '迁移守卫',
      latest: '最新',
      runs: '次运行',
      trend: '发现总数,由旧到新',
      empty: '还没有运行记录 — 在对应页面或 CLI 跑一次即可。',
      open: '打开',
    },
  },
}

export default initI18n(resources)
