import { initI18n } from '@shared/i18n'

const resources = {
  en: {
    translation: {
      title: 'Data Freshness Monitor',
      subtitle:
        'Did every table land on time? Paste a per-table update-event ' +
        'inventory (JSON or CSV with table/updated) or point at the file — ' +
        'each table is judged late, stalled or stale against rules or the ' +
        'cadence inferred from its history. Deterministic, no database ' +
        'connection.',
      file_label: 'Inventory file path',
      file_ph: 'Update events (.json/.csv), e.g. examples/freshness_demo/updates.json',
      rules_label: 'Rules file (optional)',
      rules_ph: 'e.g. examples/freshness_demo/rules.json',
      now_label: 'Evaluate at (optional)',
      now_ph: 'Default: the latest update seen, e.g. 2024-05-05 10:50:00',
      scan_btn: 'Scan file',
      text_acc: 'Scan pasted inventory',
      text_label: 'JSON / CSV update events',
      text_ph: '[{"table":"ods.orders","updated":"2024-05-01 02:40:00"}, ...]',
      scan_text_btn: 'Scan text',
      clear_btn: 'Clear',
      empty_input: 'Provide the inventory file or paste the events first.',
      bad_dir: 'Not allowed: ',
      report_ph: '▶ Per-table verdicts (late / stalled / stale) appear here.',
      home: 'Home',
      running: 'Scanning…',
    },
  },
  zh: {
    translation: {
      title: '数据新鲜度监控',
      subtitle:
        '数据都按时产出了吗？粘贴按表的更新事件清单（JSON 或 CSV，' +
        '字段 table/updated）或指向文件 — 按规则或历史推断的节奏判定每张表：' +
        '迟到、断更、过期。确定性扫描，不连数据库。',
      file_label: '清单文件路径',
      file_ph: '更新事件 (.json/.csv)，如 examples/freshness_demo/updates.json',
      rules_label: '规则文件（可选）',
      rules_ph: '如 examples/freshness_demo/rules.json',
      now_label: '评估时刻（可选）',
      now_ph: '默认取清单里最晚的更新时间，如 2024-05-05 10:50:00',
      scan_btn: '扫描文件',
      text_acc: '扫描粘贴的清单',
      text_label: 'JSON / CSV 更新事件',
      text_ph: '[{"table":"ods.orders","updated":"2024-05-01 02:40:00"}, ...]',
      scan_text_btn: '扫描文本',
      clear_btn: '清空',
      empty_input: '请先填写清单文件路径或粘贴更新事件。',
      bad_dir: '目录不在白名单: ',
      report_ph: '▶ 按表的迟到 / 断更 / 过期判定在此显示。',
      home: '首页',
      running: '扫描中…',
    },
  },
}

export default initI18n(resources)
