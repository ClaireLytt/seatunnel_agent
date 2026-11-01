import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Mask Preview',
      subtitle:
        'The last check before a data sample leaves for a test or demo ' +
        'environment. Paste the rows — sensitive columns are detected ' +
        'by name and by value shape, masked format-preserving ' +
        '(138****1234, a***@host), and shown before and after. Nothing ' +
        'leaves the process.',
      data_label: 'Data rows (CSV with header, or JSONL)',
      data_ph: 'user_id,mobile,email\n1001,13812340001,a@b.com',
      rows_label: 'Preview rows',
      run_btn: 'Preview masks',
      clear_btn: 'Clear',
      empty_input: 'Paste the data rows first.',
      report_ph: '▶ Masking rules and masked rows appear here.',
      llm_label: 'LLM policy note (needs an API key; metadata only)',
      home: 'Home',
      running: 'Masking…',
    },
  },
  zh: {
    translation: {
      title: '脱敏预览',
      subtitle:
        '数据样例外发测试、演示环境前的最后一道检查。粘贴数据行 — 列名' +
        '与值形态双判定敏感列，保格式脱敏（138****1234、a***@host），' +
        '前后对照展示。数据不出进程。',
      data_label: '数据行（CSV 带表头，或 JSONL）',
      data_ph: 'user_id,mobile,email\n1001,13812340001,a@b.com',
      rows_label: '预览行数',
      run_btn: '生成脱敏预览',
      clear_btn: '清空',
      empty_input: '请先粘贴数据行。',
      report_ph: '▶ 脱敏规则与脱敏后样例在此显示。',
      llm_label: 'LLM 策略说明（需 API key,只发规则元数据）',
      home: '首页',
      running: '脱敏中…',
    },
  },
}

export default initI18n(resources)
