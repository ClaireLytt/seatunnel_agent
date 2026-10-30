import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/data/config_migrate/ui.py). The legacy `title` markdown is split
// into title (heading) + subtitle (body); backend-rendered report keys stay
// in Python (report.py _MSG).
const resources = {
  en: {
    translation: {
      title: 'DataX/Sqoop → SeaTunnel',
      subtitle:
        'Paste a DataX job JSON or a sqoop command line and get a ' +
        'SeaTunnel config plus migration notes. Rule-based and ' +
        'deterministic — no LLM, no database connection.',
      job_label: 'DataX job JSON / sqoop command',
      job_ph: 'Paste the DataX job json, or e.g. sqoop import --connect …',
      migrate_btn: 'Migrate',
      batch_acc: 'Batch migrate a directory',
      dir_label: 'Job directory',
      dir_ph: 'Directory with *.json / sqoop scripts (recursive)',
      out_label: 'Output directory (optional)',
      out_ph: 'Writes mirrored *.conf files when set',
      batch_btn: 'Batch migrate',
      conf_label: 'SeaTunnel config',
      empty: 'Paste a DataX job or sqoop command first.',
      bad_dir: 'Not a directory: ',
      home: 'Home',
      copy: 'Copy',
      copied: 'Copied',
      running: 'Migrating…',
    },
  },
  zh: {
    translation: {
      title: 'DataX/Sqoop → SeaTunnel',
      subtitle:
        '粘贴 DataX job JSON 或 sqoop 命令行，得到 SeaTunnel 配置 + ' +
        '迁移说明清单。规则驱动、确定性——不调用 LLM、不连接数据库。',
      job_label: 'DataX job JSON / sqoop 命令',
      job_ph: '粘贴 DataX job json，或如 sqoop import --connect …',
      migrate_btn: '迁移',
      batch_acc: '批量迁移目录',
      dir_label: '任务目录',
      dir_ph: '包含 *.json / sqoop 脚本的目录（递归）',
      out_label: '输出目录（可选）',
      out_ph: '填写后按原结构写出 *.conf',
      batch_btn: '批量迁移',
      conf_label: 'SeaTunnel 配置',
      empty: '请先粘贴 DataX job 或 sqoop 命令。',
      bad_dir: '不是有效目录: ',
      home: '首页',
      copy: '复制',
      copied: '已复制',
      running: '迁移中…',
    },
  },
}

export default initI18n(resources)
