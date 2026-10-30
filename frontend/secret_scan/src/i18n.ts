import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/devops/secret_scan/ui.py). The legacy `title` markdown is split
// into title (heading, 🔑 glyph moves next to the h1) + subtitle. Directory
// scanning stays a CLI affair (the REST API refuses to walk directories),
// so the legacy dir_* keys are replaced by a single CLI hint (dir_hint).
// Report wording stays in Python (report.py) and arrives localized.
const resources = {
  en: {
    translation: {
      title: 'Secret Scan',
      subtitle:
        'Find leaked credentials in code & config — provider tokens ' +
        '(AWS / GitHub / Slack / Aliyun …), private keys, password ' +
        'assignments, DSN-embedded passwords and high-entropy strings. ' +
        'Previews are masked; placeholders are filtered.',
      text_label: 'Text to scan',
      text_ph: 'Paste a config / env file / code snippet…',
      scan_btn: 'Scan',
      dir_hint: 'Directory scan & CI gate (CLI):',
      report_ph: '▶ Findings appear here — severity, rule, file:line and a masked preview.',
      empty_text: 'Paste some text first.',
      running: 'Scanning…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '敏感凭证扫描',
      subtitle:
        '找出代码与配置里的泄漏凭证 — 云厂商 token（AWS / GitHub / ' +
        'Slack / 阿里云…）、私钥块、明文密码赋值、DSN 内嵌密码与' +
        '高熵字符串。预览已脱敏，占位符自动过滤。',
      text_label: '待扫描文本',
      text_ph: '粘贴配置 / env 文件 / 代码片段…',
      scan_btn: '扫描',
      dir_hint: '目录扫描与 CI 门禁（命令行）：',
      report_ph: '▶ 扫描后在此显示结果 — 严重度、规则、文件:行号与脱敏预览。',
      empty_text: '请先粘贴文本。',
      running: '扫描中…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
