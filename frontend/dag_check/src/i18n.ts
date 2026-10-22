import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/dag_check/ui.py). The legacy `title` markdown is split
// into title (heading, 🗓️ glyph moves next to the h1) + subtitle.
// Report wording stays in Python (i18n.py/report.py) and arrives localized.
const resources = {
  en: {
    translation: {
      title: 'Scheduling DAG Health Check',
      subtitle:
        'Build the job DAG from SQL lineage and report what breaks ' +
        'a scheduler — cycles, mid-layer tables nobody produces or ' +
        'consumes — plus execution batches and the critical path. ' +
        'No scheduler connection, nothing executed.',
      dir_label: 'SQL directory',
      dir_ph:
        'Directory containing *.sql (scanned recursively), ' +
        'e.g. examples/dagcheck_demo',
      st_label: 'SeaTunnel config directory (optional)',
      st_ph: 'Merge source→sink lineage from *.conf files',
      dialect_label: 'SQL dialect',
      check_btn: 'Check DAG',
      empty_dir: '⚠️ Provide a SQL directory first.',
      bad_dir: '⚠️ Not a directory: ',
      request_failed: '⚠️ Request failed: ',
      running: 'Checking…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '调度 DAG 体检',
      subtitle:
        '从 SQL 血缘构建作业 DAG，报告会卡住调度器的问题 — ' +
        '依赖成环、没人产出/没人消费的中间层表 — 并给出执行分批' +
        '与关键路径。不连接调度系统、不执行任何作业。',
      dir_label: 'SQL 目录',
      dir_ph: '包含 *.sql 的目录（递归扫描），如 examples/dagcheck_demo',
      st_label: 'SeaTunnel 配置目录（可选）',
      st_ph: '合并 *.conf 的 source→sink 血缘',
      dialect_label: 'SQL 方言',
      check_btn: '体检 DAG',
      empty_dir: '⚠️ 请先填写 SQL 目录。',
      bad_dir: '⚠️ 不是有效目录: ',
      request_failed: '⚠️ 请求失败: ',
      running: '体检中…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
