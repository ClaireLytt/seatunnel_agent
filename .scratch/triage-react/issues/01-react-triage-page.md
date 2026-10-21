# 01: React 页完整 + /run demo 默认值 + manifest 切换

**What to build:** ① 后端小改:run 请求 issues 字段可空(None),未提供时服务端加载 demo 历史 JSONL(examples/triage_demo/issues.jsonl,load_issues),显式 [] = 无历史;附 TestClient 测试(省略 issues 时查重命中 demo 库已知条目;[] 时无 dup;既有 503/200 回归)。② React 页:/triage → title/body 输入 + Triage 按钮 + running 提示 → Markdown 报告(ReportView 渲 report 字段);空 title 本地拦截(empty);503/502 ⚠️ detail;en/zh 平移 ui 的 _I18N。manifest external=True, render="",api= 保留;workspace 目录 frontend/issue_triage,vite base '/triage/'。engine/report 零改动。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] /run 省略 issues → demo 历史查重生效;[] → 无历史;回归不破
- [ ] frontend/issue_triage workspace 建立并入 workspaces(对标 doc_qa 骨架)
- [ ] 输入/Triage/running/报告/拦截/错误显示可用;manifest 切换完成
- [ ] npm lint + build、ruff/mypy、定向 pytest(test_issue_triage/test_registry/test_hub_pages)通过
