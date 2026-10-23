import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Release Notes',
      subtitle:
        'Grouped changelog from conventional commits (type(scope)!: subject) ' +
        'plus a semver bump suggestion (breaking → major, feat → minor, ' +
        'else patch). Deterministic; the LLM polish pass is optional.',
      log_label: 'Commit log (sha<TAB>subject per line)',
      log_ph: 'a1b2c3d\tfeat(ui): two-level hub\nd4e5f6a\tfix: handle empty config…',
      repo_btn: 'Load from this repo',
      version_label: 'Current version (optional)',
      polish_label: 'LLM polish (needs an API key)',
      gen_btn: 'Generate notes',
      clear_btn: 'Clear',
      report_ph: '▶ The grouped changelog and version suggestion appear here.',
      empty_log: '⚠️ Paste a commit log first.',
      home: 'Home',
      running: 'Generating…',
    },
  },
  zh: {
    translation: {
      title: '发布助手',
      subtitle:
        '按 conventional commits（type(scope)!: subject）分组生成 changelog，' +
        '并给出语义化版本建议（breaking → major，feat → minor，否则 patch）。' +
        '确定性生成；LLM 润色可选。',
      log_label: '提交记录（每行 sha<TAB>subject）',
      log_ph: 'a1b2c3d\tfeat(ui): two-level hub\nd4e5f6a\tfix: handle empty config…',
      repo_btn: '读取本仓库',
      version_label: '当前版本（可选）',
      polish_label: 'LLM 润色（需配置 API key）',
      gen_btn: '生成发布说明',
      clear_btn: '清空',
      report_ph: '▶ 生成后在此显示分组 changelog 与版本建议。',
      empty_log: '⚠️ 请先粘贴提交记录。',
      home: '首页',
      running: '生成中…',
    },
  },
}

export default initI18n(resources)
