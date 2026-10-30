import { initI18n } from '@shared/i18n'

// Copy ported verbatim from the Gradio page's _I18N
// (seatunnel_agent/agents/ai/issue_triage/ui.py) — title split into
// title+subtitle. `running` has no Gradio counterpart; wording follows
// the doc_qa page's `running` key. `no_key` is not ported: the 503
// response's `detail` carries that notice and the page shows detail.
const resources = {
  en: {
    translation: {
      title: 'Issue Triage Agent',
      subtitle:
        'Paste a new issue: the agent searches past issues for duplicates (BM25), greps the codebase, checks the docs — then proposes labels, priority and a draft reply. History defaults to the bundled demo; point the CLI at your own JSONL.',
      tLabel: 'Issue title',
      bLabel: 'Issue body',
      runBtn: 'Triage',
      reportPh: '▶ Labels, duplicates, priority and the draft reply appear here.',
      empty: 'Type a title first.',
      running: 'Triaging the issue…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: 'Issue 分诊 Agent',
      subtitle:
        '粘贴一条新 issue:agent 自己在历史 issue 里查重(BM25)、grep 代码定位模块、查文档,然后给出标签、优先级与草拟回复。历史默认用内置 demo;CLI 可指定你自己的 JSONL。',
      tLabel: 'Issue 标题',
      bLabel: 'Issue 正文',
      runBtn: '分诊',
      reportPh: '▶ 标签、疑似重复、优先级与草拟回复在此显示。',
      empty: '请先输入标题。',
      running: '正在分诊该 issue…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
