# 02: React 页完整 + manifest 切换

**What to build:** /codefix React 页:左列 path/tests/instruction 输入 + 步数 Slider(4–20 默认 12)+ 运行按钮;右列报告区——SSE step 行逐条追加(step_line 文案),终态 ReportView 渲染完整 Markdown 报告;空 path 本地拦截(empty);403/错误 ⚠️ detail;en/zh 平移 Gradio _I18N(title/path_label/tests_label/tests_ph/inst_label/steps_label/run_btn/report_ph/empty/no_key/step_line)。manifest external=True, render="",api= 挂 router;workspace 目录 frontend/code_fix,vite base '/codefix/'。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] frontend/code_fix workspace 建立并入 workspaces(对标 prompt_lab 骨架 + orchestrator 的 postSSE 用法)
- [ ] 输入/Slider/运行/流式步骤/终态报告/拦截/错误显示可用
- [ ] manifest 切换完成,/codefix 路由不变
- [ ] npm lint + build、ruff/mypy、定向 pytest(test_code_fix/test_registry/test_hub_pages)通过
