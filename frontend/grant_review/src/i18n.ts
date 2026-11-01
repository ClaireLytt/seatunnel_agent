import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Grant Review',
      subtitle:
        'Should this permission request go through? Paste the ' +
        'application JSON (applicant, role, purpose, tables with ' +
        'columns, duration, write flag — one or a list) — columns are ' +
        'graded against a sensitivity vocabulary and every application ' +
        'gets a transparent risk score with approve / downgrade (and ' +
        'the concrete cuts) / reject. No database connection.',
      application_label: 'Application JSON (object or list)',
      application_ph: '{"applicant":"zhang3","role":"analyst","purpose":"...","tables":[...]}',
      run_btn: 'Review',
      clear_btn: 'Clear',
      empty_input: 'Paste the application first.',
      report_ph: '▶ Risk scores and decisions appear here.',
      llm_label: 'LLM per-application replies (needs an API key)',
      home: 'Home',
      running: 'Reviewing…',
    },
  },
  zh: {
    translation: {
      title: '权限申请审核',
      subtitle:
        '这份权限申请该不该批？粘贴申请单 JSON（申请人、角色、用途、' +
        '表与列、期限、是否写权限，单份或列表）— 列按敏感级词表分级，' +
        '每份申请透明打风险分，给出批准/降级批准（附具体降级建议）/' +
        '拒绝。不连库。',
      application_label: '申请单 JSON（单份或列表）',
      application_ph: '{"applicant":"zhang3","role":"analyst","purpose":"...","tables":[...]}',
      run_btn: '审核',
      clear_btn: '清空',
      empty_input: '请先粘贴申请单。',
      report_ph: '▶ 风险分与审批结论在此显示。',
      llm_label: 'LLM 逐份回复草稿（需 API key）',
      home: '首页',
      running: '审核中…',
    },
  },
}

export default initI18n(resources)
