# 02: React 页完整 + manifest 切换

**What to build:** /webtask React 页:左列 goal textarea(goal_ph 占位)+ url 输入(默认 hub 自身 "/" 同源地址或 127.0.0.1:7860,对齐旧页)+ 步数 Slider 4–25 默认 15 + 运行按钮;右列报告区:SSE step 行逐条追加(step_line 文案),终态显示 success/fail + reply(ReportView)+ 步骤列表;空 goal 本地拦截(empty);403/错误 ⚠️ detail。i18n 平移 ui 的 _I18N;manifest external=True, render="";workspace 目录 frontend/web_task,vite base '/webtask/'(对标 code_fix 骨架 + postSSE)。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] workspace 建立并入 workspaces;输入/Slider/运行/流式/终态/拦截/错误可用
- [ ] manifest 切换完成,/webtask 路由不变
- [ ] npm lint + build、ruff/mypy、定向 pytest(test_web_task/test_registry/test_hub_pages)通过
