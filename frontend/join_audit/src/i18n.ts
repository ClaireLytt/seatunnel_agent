import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Join Audit',
      subtitle:
        'A join that silently drops a third of the rows, or multiplies ' +
        'them, is the most common invisible incident. Paste both sides ' +
        'and the key — match rates, orphan keys, null keys and the row ' +
        'explosion come back graded, before the JOIN ships.',
      left_label: 'Left rows (CSV with header, or JSONL)',
      right_label: 'Right rows (CSV with header, or JSONL)',
      keys_label: 'Join keys (k, or left_key=right_key, comma-combined)',
      data_ph: 'id,value\n1,a',
      run_btn: 'Audit join',
      clear_btn: 'Clear',
      empty_input: 'Paste both sides and the join key first.',
      report_ph: '▶ Match rates, orphans and explosion appear here.',
      llm_label: 'LLM join review (needs an API key; metrics only)',
      home: 'Home',
      running: 'Auditing…',
    },
  },
  zh: {
    translation: {
      title: '关联质量审计',
      subtitle:
        '悄悄丢掉三分之一行、或把行数翻倍的 JOIN，是数仓最常见的隐形' +
        '事故。粘贴两侧数据和关联键 — 匹配率、孤儿键、空键、行数爆炸' +
        '系数逐项分级给出，JOIN 上线前最后一道检查。',
      left_label: '左表数据（CSV 带表头，或 JSONL）',
      right_label: '右表数据（CSV 带表头，或 JSONL）',
      keys_label: '关联键（同名写 k,异名写 lk=rk,逗号组合）',
      data_ph: 'id,value\n1,a',
      run_btn: '开始审计',
      clear_btn: '清空',
      empty_input: '请先粘贴两侧数据与关联键。',
      report_ph: '▶ 匹配率、孤儿键与爆炸系数在此显示。',
      llm_label: 'LLM 关联评审（需 API key,只发指标）',
      home: '首页',
      running: '审计中…',
    },
  },
}

export default initI18n(resources)
