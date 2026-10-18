# Gradio 页迁移 React 清单

把一个 agent 页从 Gradio Blocks 迁到 React 静态挂载时的完整触点清单。
先例:text2sql(7618468 → 47c7032)、uitest、sql_review(8d1d456 → d6e72ef,
批次报告 docs/reports/20261017-sqlreview-react-migration.md)。

## 新建(对标 frontend/uitest)

1. `frontend/<name>/` workspace:复制 uitest 骨架;vite `base: '/<route>/'`,
   dev proxy 指到 `/api/<name>`;`frontend/package.json` workspaces 加名字。
2. 复用 `@shared`:theme.css(engineering-paper)、tailwind-preset、
   components/card、lang.ts(st-lang cookie)、sse.ts(长任务才用)。
3. i18n:i18next 资源从 Python i18n 字典逐字平移;语言初始化
   `langFromCookie()`。
4. REST:页面直接 fetch;router 在 `hub/ui.py` launch 后无条件挂载
   (uitest/sql_review 模式),manifest 的 `api=` 留空以免 --api 环重复挂载。

## 切换

5. manifest:`external=True`,`render=""`;静态挂载走
   `registry.frontend_dist` 约定,未 build 自动出提示页。
   **workspace 目录名必须等于 manifest.name**(datacompare 曾因目录名用了
   路由名而挂载落空);页面测试取 dist 路径用 `registry.frontend_dist()`。
   前端改动后必须重建 dist 并重启 hub:`seatunnel-agent ui --build` 一步完成。

## 退役旧页(爆炸半径,逐项核对)

6. 删 `<agent>/ui.py`;Python i18n 只删 UI-chrome key,后端渲染用的 key
   (报告模板、agent/fixer 消息)保留。
7. `hub/css.py`:删该页的 body:has(.st-xxx-page) 滚动标记与 polish 段。
8. uitest 引擎 `ui_testing/page.py`:READY 路由映射、该页专属 LABELS、
   结果区选择器(result_container / wait_for_text / debug dump 三处)。
9. uitest 用例:`cases/<name>.yaml` 整文件 + extended/scroll/misc 等文件里
   引用该路由的散落用例;等价覆盖写成 `tests/test_<name>_page.py`
   (Playwright,照 test_uitest_page.py 的 in-process uvicorn 模式)。
10. `ui_testing/catalog.py`:AGENT_ROUTES / AGENT_LABELS(en、zh)三处。
11. 测试硬编码:`tests/test_registry.py` 的 `_DATA_API_NAMES`、
    `tests/test_ui_testing.py` 的 coverage/label 断言。
12. 跨页桥:localStorage 键(st_transpile_sql 等)机制保留,对端若仍是
    Gradio 不要动对端。

## 验证

13. 全套:ruff / mypy / pytest / `pytest -m uitest tests/test_<name>_page.py`
    / uitest smoke / 截图前后对比(`docs/reports/shots/`,旧页截图用
    `git worktree add` 到迁移前 commit 起服务,Gradio 页 Playwright 要用
    `wait_until="load"`,networkidle 因长连接不触发)/ check_workflow.py。
