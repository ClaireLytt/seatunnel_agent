import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/config_lint/ui.py). The legacy `title` markdown is split
// into title (heading) + subtitle (body); backend-rendered report keys stay
// in Python (report.py).
const resources = {
  en: {
    translation: {
      title: 'SeaTunnel Config Lint',
      subtitle:
        'Param-level lint against the built-in connector docs — unknown ' +
        'connectors/params with did-you-mean suggestions, missing required ' +
        'params, type & enum mismatches, CDC vs job.mode sanity. Parsed, ' +
        'never executed.',
      conf_label: 'Config (HOCON)',
      conf_ph: 'Paste a SeaTunnel .conf…',
      lint_btn: 'Lint config',
      dir_acc: 'Lint a directory',
      dir_label: 'Config directory',
      dir_ph: 'Directory containing *.conf (scanned recursively), ' + 'e.g. examples/conflint_demo',
      dir_btn: 'Lint directory',
      empty_conf: 'Paste a config first.',
      empty_dir: 'Provide a config directory first.',
      bad_dir: 'Not a directory: ',
      home: 'Home',
      running: 'Linting…',
    },
  },
  zh: {
    translation: {
      title: 'SeaTunnel 配置深度检查',
      subtitle:
        '基于内置连接器文档的参数级检查 — 未知连接器/参数带' +
        '「是不是想写」建议、缺失必填参数、类型与枚举校验、' +
        'CDC 与 job.mode 冲突检测。只解析不执行。',
      conf_label: '配置 (HOCON)',
      conf_ph: '粘贴 SeaTunnel .conf 配置…',
      lint_btn: '检查配置',
      dir_acc: '检查整个目录',
      dir_label: '配置目录',
      dir_ph: '包含 *.conf 的目录（递归扫描），如 examples/conflint_demo',
      dir_btn: '检查目录',
      empty_conf: '请先粘贴配置。',
      empty_dir: '请先填写配置目录。',
      bad_dir: '不是有效目录: ',
      home: '首页',
      running: '检查中…',
    },
  },
}

export default initI18n(resources)
