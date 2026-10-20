# 02: React 页最小闭环 + manifest 切换

**What to build:** 打开 /promptlab 是 React 页:prompt/system 输入、profiles 多选(GET /profiles,默认选 "(active)")、parallel 开关(默认勾选,显式传 true)、运行按钮 → running → Markdown 矩阵报告(POST /run report:true);空 prompt/空 profiles 本地拦截显示 empty_prompt/no_profiles,不发请求;400/错误以 ⚠️ 显示。manifest external=True, render="";**workspace 目录名必须 = manifest.name "prompt_lab"**,vite base '/promptlab/'。api= 留空问题:核实 hub/registry 实际挂载代码与 orchestrator/llm_eval 先例后照做并在汇报中说明。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] frontend/prompt_lab workspace 建立并入 workspaces
- [ ] 输入/多选/parallel/运行/报告/本地校验可用
- [ ] manifest 切换完成,/promptlab 路由不变
- [ ] npm lint + build、ruff/mypy、定向 pytest(test_prompt_lab/test_registry/test_hub_pages)通过
