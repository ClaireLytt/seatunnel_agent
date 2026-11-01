import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'CSV Doctor',
      subtitle:
        'The file will not parse, or opens as mojibake. Paste the raw ' +
        'text — byte-level forensics (BOM, double-encoded garble ' +
        'recovered with before/after samples, lost bytes named) plus ' +
        'structural repair (ragged rows, duplicate headers), and a ' +
        'fixed CSV comes out the other side.',
      data_label: 'Raw CSV text',
      data_ph: 'id;name;amount\n1;è®¢å•ä¸€;10.5',
      run_btn: 'Diagnose file',
      clear_btn: 'Clear',
      download_btn: 'Download fixed CSV',
      empty_input: 'Paste the raw CSV text first.',
      report_ph: '▶ Diagnosis and the repaired CSV appear here.',
      llm_label: 'LLM incident note (needs an API key; metadata only)',
      home: 'Home',
      running: 'Diagnosing…',
    },
  },
  zh: {
    translation: {
      title: 'CSV 急救',
      subtitle:
        '文件喂不进去，或一打开是乱码。粘贴原文 — 字节取证（BOM、双重' +
        '编码乱码带前后对照复原、丢失字节点名）加结构修复（列数漂移、' +
        '表头重名），另一头吐出能用的 CSV。',
      data_label: 'CSV 原文',
      data_ph: 'id;name;amount\n1;è®¢å•ä¸€;10.5',
      run_btn: '开始诊断',
      clear_btn: '清空',
      download_btn: '下载修复版 CSV',
      empty_input: '请先粘贴 CSV 原文。',
      report_ph: '▶ 诊断与修复版 CSV 在此显示。',
      llm_label: 'LLM 事故说明（需 API key,只发诊断元数据）',
      home: '首页',
      running: '诊断中…',
    },
  },
}

export default initI18n(resources)
