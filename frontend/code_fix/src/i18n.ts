import { initI18n } from '@shared/i18n'

// Copy ported verbatim from the Gradio page's _I18N
// (seatunnel_agent/agents/ai/code_fix/ui.py) — title split into
// title+subtitle. The final-report keys (ok/fail/steps/diff/noDiff/
// workdir/summary/truncated) are ported from code_fix/report.py _I18N:
// the SSE `done` event carries structured fields and the page renders
// the same information structure client-side.
const resources = {
  en: {
    translation: {
      title: 'Code Fix Agent',
      subtitle:
        'Point it at a git repo with failing tests: it runs pytest, reads the code, patches, and re-runs until green — inside a fresh git worktree (your checkout is never touched); success is verified by a final deterministic run and the diff is yours to review.',
      pathLabel: 'Repository path (must be a git repo)',
      testsLabel: 'Test selector (optional)',
      testsPh: 'e.g. tests/test_core.py::test_div',
      instLabel: 'Extra instruction (optional)',
      stepsLabel: 'Max steps',
      runBtn: 'Fix it',
      reportPh: '▶ Agent steps stream here; the diff and verdict land at the end.',
      empty: '⚠️ Provide a repository path first.',
      noKey: '⚠️ No LLM configured — set an API key on /settings.',
      stepLine: '🔧 {{i}}. {{tool}} · {{ms}} ms{{err}}',
      running: 'Running…',
      ok: '✅ Tests green',
      fail: '❌ Tests still failing',
      steps: 'Agent steps',
      diff: 'Diff (review before taking it)',
      noDiff: '(no changes were made)',
      workdir: 'Worktree',
      summary: 'Agent summary',
      truncated: '⚠️ Step limit reached.',
      testOutput: 'Final test output',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '测试自愈 Agent',
      subtitle:
        '指向一个测试失败的 git 仓库:它自己跑 pytest、读码、打补丁、复跑直到通过 — 全程在新建的 git worktree 里(你的工作区绝不被改动);是否成功以最终的确定性复跑为准,diff 供人工审阅采纳。',
      pathLabel: '仓库路径(必须是 git 仓库)',
      testsLabel: '测试选择器(可选)',
      testsPh: '如 tests/test_core.py::test_div',
      instLabel: '补充说明(可选)',
      stepsLabel: '步数上限',
      runBtn: '开始修复',
      reportPh: '▶ Agent 步骤实时显示在此;结束后给出 diff 与验收结论。',
      empty: '⚠️ 请先填写仓库路径。',
      noKey: '⚠️ 未配置 LLM — 请先到 /settings 配置 API key。',
      stepLine: '🔧 {{i}}. {{tool}} · {{ms}} ms{{err}}',
      running: '运行中…',
      ok: '✅ 测试已通过',
      fail: '❌ 测试仍未通过',
      steps: 'Agent 步骤',
      diff: '改动 Diff(采纳前请人工审阅)',
      noDiff: '(没有产生任何改动)',
      workdir: '工作副本',
      summary: 'Agent 总结',
      truncated: '⚠️ 已达步数上限。',
      testOutput: '最终测试输出',
      home: '首页',
    },
  },
}

export default initI18n(resources)
