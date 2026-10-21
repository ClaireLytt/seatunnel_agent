# 02: 退役 CI Log Triage Gradio 页并以 Playwright 页测替代

**What to build:** 旧 Gradio 页全部触点清理干净,真浏览器页测替代原 uitest 引擎用例;用户行为不变(`/ciinspect` 已是 React 页),仓库中无死代码。

**Blocked by:** 01 ci_inspect React workspace 与 cutover

**Status:** ready-for-agent

- [ ] 删除该 agent 的 Gradio ui.py;grep 无残留引用(hub、css、ui_testing page/catalog 路由与标签)
- [ ] devops.yaml 移除 CI1 用例;ui_testing 相关测试的用例计数/硬编码同步更新
- [ ] 新增页级 Playwright 测试(uitest marker):smoke、CI1 等价场景(贴失败日志得到归因报告)、空输入反馈
- [ ] 新页真浏览器截图留存(批次报告用)
- [ ] ruff/mypy/定向 pytest 通过;uitest 页测通过
