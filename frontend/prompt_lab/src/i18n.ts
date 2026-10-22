import { initI18n } from '@shared/i18n'

// Copy ported verbatim from the Gradio page's _I18N
// (seatunnel_agent/agents/ai/prompt_lab/ui.py) — title split into
// title+subtitle. `running` has no Gradio counterpart; wording follows
// the llm_eval page's `running` key.
const resources = {
  en: {
    translation: {
      title: 'Prompt Lab',
      subtitle:
        "Run one prompt across several provider profiles side-by-side — outputs, tokens, latency and diff. Profiles are saved on the Settings page; (active) is the currently configured LLM. Experiments never switch the app's active provider.",
      promptLabel: 'Prompt',
      promptPh: 'The user prompt to send to every profile…',
      systemLabel: 'System prompt (optional)',
      systemPh: 'Defaults to a plain assistant persona',
      profilesLabel: 'Profiles',
      profilesHint:
        'No saved profiles yet? Save one per provider on the <0>Settings</0> page, then reload this page.',
      reportPh:
        '▶ Results appear here after a run — per-profile outputs with tokens and latency, ready to diff.',
      parallelLabel: 'Run in parallel',
      runBtn: 'Run matrix',
      emptyPrompt: '⚠️ Type a prompt first.',
      noProfiles: '⚠️ Select at least one profile.',
      running: 'Running the matrix against the profiles…',
      diffAcc: 'Diff two profiles',
      diffA: 'From',
      diffB: 'To',
      diffBtn: 'Diff',
      histAcc: 'Experiment history',
      histBtn: 'Refresh history',
      needTwo: '⚠️ Run a matrix with ≥2 successful cells first.',
      noHistory: 'No experiments logged yet.',
      histTime: 'Time',
      histPrompt: 'Prompt',
      histProfiles: 'Profiles',
      histCells: 'Cells',
      home: 'Home',
    },
  },
  zh: {
    translation: {
      title: 'Prompt 实验室',
      subtitle:
        '同一个 Prompt 在多个模型档案上并排运行 — 对比输出、token、耗时与差异。档案在「设置」页保存;(active) 表示当前生效的 LLM。实验不会切换全局配置。',
      promptLabel: 'Prompt',
      promptPh: '发给每个档案的用户 Prompt…',
      systemLabel: 'System Prompt(可选)',
      systemPh: '默认使用通用助手人设',
      profilesLabel: '模型档案',
      profilesHint: '还没有档案?在 <0>设置</0> 页按 provider 各存一份档案,回来刷新本页即可多选对比。',
      reportPh: '▶ 运行后在此显示结果 — 各档案的输出、token 与耗时,可随后两两对比差异。',
      parallelLabel: '并行执行',
      runBtn: '运行对比',
      emptyPrompt: '⚠️ 请先输入 Prompt。',
      noProfiles: '⚠️ 至少选择一个档案。',
      running: '正在各档案上运行对比…',
      diffAcc: '对比两个档案的输出',
      diffA: '基准',
      diffB: '对比',
      diffBtn: '生成差异',
      histAcc: '实验历史',
      histBtn: '刷新历史',
      needTwo: '⚠️ 请先运行一次含 ≥2 个成功结果的对比。',
      noHistory: '还没有实验记录。',
      histTime: '时间',
      histPrompt: 'Prompt',
      histProfiles: '档案',
      histCells: '结果',
      home: '首页',
    },
  },
}

export default initI18n(resources)
