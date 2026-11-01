import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Compaction Plan',
      subtitle:
        'A thousand 2 MB files serve a query worse than eight 256 MB ' +
        'ones — and the NameNode pays for each. Paste the file ' +
        'inventory — merge candidates come back ranked by the files ' +
        'they free, with templates ready and pressure points named.',
      data_label: 'File inventory (table,partition,file_count,total_mb)',
      data_ph: 'table,partition,file_count,total_mb\nods.log,dt=2026-10-30,960,1920',
      small_label: 'Small-file threshold (avg MB)',
      target_label: 'Target file size (MB)',
      run_btn: 'Plan compaction',
      clear_btn: 'Clear',
      empty_input: 'Paste the file inventory first.',
      report_ph: '▶ Merge candidates and templates appear here.',
      llm_label: 'LLM compaction review (needs an API key)',
      home: 'Home',
      running: 'Planning…',
    },
  },
  zh: {
    translation: {
      title: '小文件治理',
      subtitle:
        '一千个 2MB 的文件比八个 256MB 的更拖查询，NameNode 还要为每个' +
        '付钱。粘贴文件清单 — 合并候选按收敛文件数排名，模板现成，' +
        '压力点点名。',
      data_label: '文件清单（table,partition,file_count,total_mb）',
      data_ph: 'table,partition,file_count,total_mb\nods.log,dt=2026-10-30,960,1920',
      small_label: '小文件阈值（均值 MB）',
      target_label: '目标文件大小（MB）',
      run_btn: '生成治理方案',
      clear_btn: '清空',
      empty_input: '请先粘贴文件清单。',
      report_ph: '▶ 合并候选与模板在此显示。',
      llm_label: 'LLM 合并评审（需 API key）',
      home: '首页',
      running: '规划中…',
    },
  },
}

export default initI18n(resources)
