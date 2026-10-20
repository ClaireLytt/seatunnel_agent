# 02: React 页最小闭环 + manifest 切换

**What to build:** 打开 /llmeval 是 React 页(engineering-paper,禁蓝紫渐变):YAML 套件编辑器(占位示例)、judge 开关、运行按钮 → running 提示 → Markdown 报告区(含回归对比);无 key 时显示 503 错误详情。manifest 切 external,workspace 目录名 = manifest.name(llm_eval),`ui --build` 可打开。对标 frontend/uitest 工程结构(表单+报告形态),复用 @shared。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] frontend/llm_eval workspace 建立并加入 workspaces
- [ ] 编辑器 + judge 开关 + 运行 + 报告渲染可用(POST /api/llmeval/run)
- [ ] manifest external=True, render="";route /llmeval 不变
- [ ] npm lint + build 通过
