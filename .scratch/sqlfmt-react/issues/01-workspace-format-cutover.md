# 01: SQL Formatter React workspace + 全功能 + API dir 扩展 + cutover

**What to build:** 用户打开 `/sqlfmt` 看到与其他 React 页同一设计语言的页面：
粘贴 SQL、选方言（7 种，默认 hive）点"格式化"得到 Markdown 报告；展开
"检查目录"输入目录（默认示例目录）得到批量检查报告（只检查不写）；
空输入/坏目录本地化提示；zh/en 与暗色全程正确。旧 Gradio 页退役，
路由与既有 REST 契约不变。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/sqlfmt-react/screenshots/
- [ ] API：POST /api/sqlfmt/format 增加可选 `dir`（sql/dir 二选一），白名单
      SQLFMT_API_ALLOWED_DIRS 前置 → 结构化 bad_dir → fmt_dir(write=False)
      → render_batch_markdown；向后兼容，带定向 API 测试
- [ ] React workspace frontend/sql_fmt（uitest 骨架 + config_lint 参照）：
      SQL 输入 + 方言下拉 + 格式化按钮 + 目录折叠区 + markdown 报告区
- [ ] i18n 字典原样搬 i18next；暗色走 @shared 主题
- [ ] cutover：manifest external/render=""/api= 置空，hub 无条件挂 router，
      删 ui.py；`seatunnel-agent ui --build` 验证页面可用
- [ ] after 截图（zh/en × 亮/暗 + 往返报告）
- [ ] ruff / mypy / 定向测试 / workspace lint+build 通过
