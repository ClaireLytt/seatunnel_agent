import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Cost Allocation',
      subtitle:
        'The question finance actually asks is who pays. Paste the ' +
        'usage inventory with unit prices — each owner gets its bill ' +
        'with the top cost drivers, unallocated spend is called out ' +
        'first, and the same inventory always yields the same bill.',
      data_label: 'Usage inventory (owner,item,storage_gb,compute_hours)',
      data_ph: 'owner,item,storage_gb,compute_hours\ntrade,dwd.orders,850,120',
      storage_label: 'Storage price (/GB)',
      compute_label: 'Compute price (/hour)',
      run_btn: 'Allocate costs',
      clear_btn: 'Clear',
      empty_input: 'Paste the usage inventory first.',
      report_ph: '▶ The per-owner bill appears here.',
      llm_label: 'LLM billing note (needs an API key)',
      home: 'Home',
      running: 'Allocating…',
    },
  },
  zh: {
    translation: {
      title: '成本分摊',
      subtitle:
        '财务真正要问的是"谁来付"。粘贴用量清单和单价 — 逐归属方出账单' +
        '和各家成本大头，无主开销优先点名，同清单必得同账单。',
      data_label: '用量清单（owner,item,storage_gb,compute_hours）',
      data_ph: 'owner,item,storage_gb,compute_hours\ntrade,dwd.orders,850,120',
      storage_label: '存储单价（/GB）',
      compute_label: '计算单价（/时）',
      run_btn: '开始分摊',
      clear_btn: '清空',
      empty_input: '请先粘贴用量清单。',
      report_ph: '▶ 逐归属方账单在此显示。',
      llm_label: 'LLM 账单通报（需 API key）',
      home: '首页',
      running: '计算中…',
    },
  },
}

export default initI18n(resources)
