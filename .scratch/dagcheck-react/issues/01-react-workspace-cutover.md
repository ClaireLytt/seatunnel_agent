# 01: dag_check React workspace 与完整切换

**What to build:** 用户访问 /dagcheck 看到 React 版页面(风格与其他已迁页一致):SQL 目录(默认 examples/dagcheck_demo)、SeaTunnel 配置目录(可选)、方言下拉(7 项,hive 默认)、"体检 DAG"按钮、markdown 报告区;双语随 st-lang cookie 切换;Gradio 旧页退役。先抓旧页截图再删。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] frontend/dag_check workspace(uitest 骨架复制,vite base '/dagcheck/',根 workspaces 注册,@shared 复用,无蓝紫色)
- [ ] 页面调用既有 POST /api/dagcheck/check 渲染 report markdown;坏目录/空输入提示文案与现行为一致
- [ ] i18next 资源与 dag_check/i18n.py 对齐;manifest external=True、render=""、api="" 清空;router 改 hub/ui.py 挂载(防双挂载)
- [ ] 退役:删 ui.py;清 hub/css.py 页面段、ui_testing/page.py 三处、catalog.py 两处;裁剪 UI-chrome i18n keys(保留报告模板 keys)
- [ ] 迁移前(Gradio)/后(React)截图落盘 docs/reports/shots
- [ ] `seatunnel-agent ui --build` 构建通过;ruff/mypy + 定向测试(现有 dag_check API/checker 测试)通过
