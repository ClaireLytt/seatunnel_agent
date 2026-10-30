import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Dependency Health',
      subtitle:
        'Declared vs installed, unpinned specs, duplicate pins and a ' +
        'license inventory — offline. CI gate: ' +
        'seatunnel-agent depcheck --fail-on high.',
      text_label: 'pyproject.toml or requirements.txt content',
      text_ph: 'Paste a pyproject.toml ([project] deps) or requirements.txt…',
      check_btn: 'Analyze',
      self_btn: 'Check this project',
      clear_btn: 'Clear',
      report_ph: '▶ Findings and the dependency inventory appear here.',
      empty_text: 'Paste some metadata first.',
      home: 'Home',
      running: 'Analyzing…',
    },
  },
  zh: {
    translation: {
      title: '依赖体检',
      subtitle:
        '声明 vs 实装、未钉版本、重复/冲突与 License 清单 — 全离线。' +
        'CI 门禁：seatunnel-agent depcheck --fail-on high。',
      text_label: 'pyproject.toml 或 requirements.txt 内容',
      text_ph: '粘贴 pyproject.toml（[project] 依赖）或 requirements.txt…',
      check_btn: '检查',
      self_btn: '检查本项目',
      clear_btn: '清空',
      report_ph: '▶ 检查后在此显示问题与依赖清单。',
      empty_text: '请先粘贴依赖声明。',
      home: '首页',
      running: '检查中…',
    },
  },
}

export default initI18n(resources)
