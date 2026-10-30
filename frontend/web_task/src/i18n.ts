import { initI18n } from '@shared/i18n'

// Copy ported verbatim from the Gradio page's _I18N
// (seatunnel_agent/agents/ai/web_task/ui.py:15-49) — title split into
// title+subtitle. `noKey` is kept for parity although the no-LLM case
// now arrives as a backend SSE `error` event (api.py _NO_KEY) and is
// shown via `notice`. `stepLine` drops the `{inp}` slot: the SSE step
// event carries no tool input. The terminal ok/fail wording is new —
// the Gradio page emitted a bare ✅/❌ mark from render.
const resources = {
  en: {
    translation: {
      title: 'Web Task Agent',
      subtitle:
        'Give it a goal and a start URL: the agent drives a real (headless) browser — snapshot of the numbered interactive elements → click/fill → observe again. Navigation is confined to the start URL’s origin. Try it on this platform’s own pages.',
      goalLabel: 'Goal',
      goalPh: 'e.g. open the SQL Formatter page and format SELECT 1',
      urlLabel: 'Start URL',
      stepsLabel: 'Max steps',
      runBtn: 'Run task',
      reportPh: '▶ Actions stream here; the agent ends with DONE/FAILED.',
      empty: 'Provide a goal and a URL first.',
      noKey: 'No LLM configured — set an API key on /settings.',
      stepLine: '🖱️ {{i}}. {{tool}} · {{ms}} ms{{err}}',
      running: 'Running…',
      ok: '✅ Task done',
      fail: '❌ Task failed',
      steps: 'Agent steps',
      reply: 'Agent reply',
      truncated: 'Step limit reached.',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '网页操作 Agent',
      subtitle:
        '给目标和起始 URL:agent 驱动一个真实(无头)浏览器 — 获取编号元素快照 → 点击/填表 → 再观察。导航默认限制在起始同源。可以拿本平台自己的页面试。',
      goalLabel: '任务目标',
      goalPh: '例如:打开 SQL 格式化页,把 SELECT 1 格式化一次',
      urlLabel: '起始 URL',
      stepsLabel: '步数上限',
      runBtn: '执行任务',
      reportPh: '▶ 操作步骤实时显示;结束时给出 DONE/FAILED。',
      empty: '请先填写目标与 URL。',
      noKey: '未配置 LLM — 请先到 /settings 配置 API key。',
      stepLine: '🖱️ {{i}}. {{tool}} · {{ms}} ms{{err}}',
      running: '运行中…',
      ok: '✅ 任务完成',
      fail: '❌ 任务失败',
      steps: 'Agent 步骤',
      reply: 'Agent 答复',
      truncated: '已达步数上限。',
      home: '首页',
    },
  },
}

export default initI18n(resources)
