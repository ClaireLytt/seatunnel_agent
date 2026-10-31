import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Config Diff',
      subtitle:
        'What actually differs between dev and prod? Paste both configs ' +
        '(SeaTunnel HOCON, JSON or flat properties — comments and ' +
        'ordering never count) — every added, removed or changed key ' +
        'comes back graded by what it controls, with secrets masked. No ' +
        'environment connection.',
      left_label: 'Left config (e.g. dev)',
      right_label: 'Right config (e.g. prod)',
      config_ph: 'env { parallelism = 2 }\nsource { ... }\nsink { ... }',
      run_btn: 'Diff',
      clear_btn: 'Clear',
      empty_input: 'Paste both configs first.',
      report_ph: '▶ Graded semantic differences appear here.',
      llm_label: 'LLM drift review (needs an API key)',
      home: 'Home',
      running: 'Diffing…',
    },
  },
  zh: {
    translation: {
      title: '配置漂移对比',
      subtitle:
        'dev 和 prod 到底差在哪？粘贴两份配置（SeaTunnel HOCON/JSON/' +
        '扁平 properties，注释与顺序不计）— 新增/删除/改值逐键返回并按' +
        '所控内容分级，密钥自动脱敏。不连环境。',
      left_label: '左侧配置（如 dev）',
      right_label: '右侧配置（如 prod）',
      config_ph: 'env { parallelism = 2 }\nsource { ... }\nsink { ... }',
      run_btn: '对比',
      clear_btn: '清空',
      empty_input: '请先粘贴两份配置。',
      report_ph: '▶ 分级语义差异在此显示。',
      llm_label: 'LLM 发布评审意见（需 API key）',
      home: '首页',
      running: '对比中…',
    },
  },
}

export default initI18n(resources)
