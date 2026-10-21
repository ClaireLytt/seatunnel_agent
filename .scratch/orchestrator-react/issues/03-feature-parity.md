# 03: 功能对齐——示例按钮、agents 面板、会话恢复、i18n

**What to build:** 三个示例按钮(review/chain/pii)一键填入并发送;可折叠 "Routable agents" 面板展示可路由 agent;刷新页面后会话记录恢复;en/zh 文案随 st-lang cookie 切换(文案从 Gradio ui 字典平移)。完成后 1:1 验收清单全绿。

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] 示例按钮×3 可一键发送
- [ ] Routable agents 折叠面板(数据来自 agents API)
- [ ] 刷新后会话恢复
- [ ] en/zh i18n 完整,随 st-lang cookie
- [ ] npm lint + build、ruff/mypy/定向 pytest 通过
