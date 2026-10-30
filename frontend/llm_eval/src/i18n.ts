import { initI18n } from '@shared/i18n'

const SUITE_PH = `suite: my-golden
cases:
  - id: t1
    agent: raw_prompt
    ...`

// Copy ported verbatim from the Gradio page's _I18N
// (seatunnel_agent/agents/ai/llm_eval/ui.py) — title split into title+subtitle.
const resources = {
  en: {
    translation: {
      title: 'LLM Eval',
      subtitle:
        "Golden suites for the platform's LLM features — the suite runs against the configured LLM, deterministic checkers score every case, and history powers the regression gate (seatunnel-agent llmeval --fail-on regression).",
      suiteLabel: 'Suite (YAML)',
      suitePh: SUITE_PH,
      demoBtn: 'Load demo suite',
      validateBtn: 'Validate suite (no LLM)',
      validOk: '✅ Suite is valid: {{n}} cases · agents: {{agents}}',
      trendAcc: 'Score trend',
      trendBtn: 'Refresh trend',
      noRuns: 'No eval runs logged yet.',
      judgeLabel: 'Run judge checks (advisory)',
      runBtn: 'Run suite',
      reportPh:
        '▶ Results appear here after a run — per-case scores, failed checks, and the regression verdict vs the previous run.',
      emptySuite: 'Paste a YAML suite first.',
      running: 'Running suite against the LLM…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: 'LLM 评测',
      subtitle:
        '平台 LLM 功能的黄金用例集 — 套件在当前配置的 LLM 上运行,确定性检查器自动打分,历史记录支撑回归门禁(seatunnel-agent llmeval --fail-on regression)。',
      suiteLabel: '评测套件(YAML)',
      suitePh: SUITE_PH,
      demoBtn: '载入示例套件',
      validateBtn: '校验套件(不调 LLM)',
      validOk: '✅ 套件合法:{{n}} 个 case · agent:{{agents}}',
      trendAcc: '分数趋势',
      trendBtn: '刷新趋势',
      noRuns: '还没有评测运行记录。',
      judgeLabel: '运行 judge 评分(仅参考)',
      runBtn: '运行套件',
      reportPh: '▶ 运行后在此显示结果 — 每个 case 的得分、未通过的检查,以及与上次运行的回归对比。',
      emptySuite: '请先粘贴 YAML 套件。',
      running: '正在用 LLM 运行套件…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
