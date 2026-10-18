# 01: React workspace + 单条迁移路径

**What to build:** 新建 frontend/config_migrate workspace(uitest 骨架、@shared 主题、workspace 登记、vite base/proxy),新建 /api/config_migrate REST router(单条迁移端点,复用 migrator.migrate_text 与 report 渲染)并在 hub launch 无条件挂载;页面实现单条输入 + Migrate 按钮 + yaml 输出(语法高亮,先查 sql_review/text2sql 高亮先例,有则复用)+ Markdown 报告 + 错误提示;i18next 资源从 _I18N 平移,langFromCookie 初始化。此票完成后经 vite dev 或构建后可演示单条迁移全链路(Gradio 页暂保留并存)。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] frontend/config_migrate 构建通过(npm run lint + build --workspace config_migrate)
- [ ] API 单条迁移端点 pytest(TestClient)覆盖成功/不支持输入
- [ ] 页面展示 yaml(高亮+可复制)与报告,失败有错误提示
- [ ] 中英文随 st-lang cookie 切换
- [ ] ruff/mypy + 定向测试通过
