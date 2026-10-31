import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Suite Overview',
      subtitle:
        'The agent suites in one place. Every card opens the agent; ' +
        'arrows mark the built-in handoffs between them.',
      suite_quality: 'Quality anomalies',
      suite_governance: 'Asset governance',
      suite_realtime: 'Realtime pipeline',
      suite_scheduling: 'Scheduling ops',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '套件总览',
      subtitle: '各套件一页看完。点卡片直达 agent；箭头是它们之间的内置交接。',
      suite_quality: '质量异常',
      suite_governance: '资产治理',
      suite_realtime: '实时链路',
      suite_scheduling: '调度运维',
      home: '首页',
    },
  },
}

export default initI18n(resources)
