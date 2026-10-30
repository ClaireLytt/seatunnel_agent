import { initI18n } from '@shared/i18n'

// UI-chrome keys ported verbatim from the legacy _I18N dict
// (agents/devops/ci_inspect/ui.py). The legacy `title` markdown is split
// into title (heading, 🧭 glyph moves next to the h1) + subtitle.
// home/running are new chrome. Report wording stays in Python
// (report.py) and arrives localized.
const resources = {
  en: {
    translation: {
      title: 'CI Log Triage',
      subtitle:
        'Cluster failed-job logs into Top-N root causes (numbers / ' +
        'paths / hashes masked before grouping), and analyze runs ' +
        'metadata for flaky jobs (same commit, both pass & fail) ' +
        'and duration drift. Offline — paste what `gh run view ' +
        '--log-failed` / `gh api .../actions/runs` gives you.',
      log_label: 'Failed job log',
      log_ph: "Paste one job's log (GitHub Actions timestamps are fine)…",
      name_label: 'Job name',
      runs_acc: 'Runs metadata (flaky & duration)',
      runs_label: 'Runs JSON',
      runs_ph:
        '[{"workflow":"tests","conclusion":"failure",' +
        '"head_sha":"abc1234","duration_s":312}, …]',
      analyze_btn: 'Analyze',
      report_ph: '▶ Root-cause clusters, flaky jobs and duration drift appear here.',
      empty: 'Paste a log or runs JSON first.',
      running: 'Analyzing…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: 'CI 日志诊断',
      subtitle:
        '把失败作业日志聚类成 Top-N 根因(聚类前先掩掉数字 / 路径 / ' +
        '哈希),并对运行元数据做 flaky 识别(同一提交又过又挂)与' +
        '时长漂移分析。全离线 — 粘贴 `gh run view --log-failed` / ' +
        '`gh api .../actions/runs` 的输出即可。',
      log_label: '失败作业日志',
      log_ph: '粘贴一个作业的日志(带 GitHub Actions 时间戳也可以)…',
      name_label: '作业名',
      runs_acc: '运行元数据(flaky 与时长)',
      runs_label: 'Runs JSON',
      runs_ph:
        '[{"workflow":"tests","conclusion":"failure",' +
        '"head_sha":"abc1234","duration_s":312}, …]',
      analyze_btn: '分析',
      report_ph: '▶ 分析后在此显示根因聚类、flaky 作业与时长漂移。',
      empty: '请先粘贴日志或 runs JSON。',
      running: '分析中…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
