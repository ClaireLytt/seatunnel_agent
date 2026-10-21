import { initI18n } from '@shared/i18n'

// Copy ported verbatim from the Gradio page's _I18N
// (seatunnel_agent/agents/ai/doc_qa/ui.py) — title split into
// title+subtitle. `running` has no Gradio counterpart; wording follows
// the llm_eval page's `running` key.
const resources = {
  en: {
    translation: {
      title: 'Doc Q&A',
      subtitle:
        "Ask about SeaTunnel connectors and this project's docs — offline BM25 retrieval with citations; tick the LLM box for a synthesized answer grounded in the retrieved excerpts only.",
      qLabel: 'Question',
      qPh: 'e.g. How do I configure the Jdbc sink batch size?',
      llmLabel: 'LLM synthesis (needs an API key)',
      askBtn: 'Ask',
      reportPh: '▶ The answer and its sources appear here.',
      empty: '⚠️ Type a question first.',
      running: 'Searching the docs for an answer…',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: '文档问答',
      subtitle:
        '询问 SeaTunnel 连接器与本项目文档 — 离线 BM25 检索,带来源引用;勾选 LLM 可基于检索片段综合作答(只依据片段,不编造参数)。',
      qLabel: '问题',
      qPh: '例如:Jdbc sink 的批量写入参数怎么配?',
      llmLabel: 'LLM 综合作答(需 API key)',
      askBtn: '提问',
      reportPh: '▶ 回答与来源在此显示。',
      empty: '⚠️ 请先输入问题。',
      running: '正在检索文档并生成回答…',
      home: '首页',
    },
  },
}

export default initI18n(resources)
