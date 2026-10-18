# Ticket 01: React workspace + lint 全功能 + cutover 退役

## 范围

1. **前置截图**：迁移前用脚本对 Gradio `/conflint` 截 before 截图（zh/en、亮/暗），
   存 `.scratch/conflint-react/screenshots/`（参照 config_migrate 的 shot_old.py）。
2. **新建 workspace** `frontend/config_lint/`（目录名 = manifest.name）：
   复制 uitest 骨架，vite `base: '/conflint/'`，dev proxy 到 `/api/conflint`，
   加入 `frontend/package.json` workspaces；复用 `@shared`（theme.css、
   tailwind-preset、card、lang.ts）。
3. **页面功能 1:1**（对照 `agents/data/config_lint/ui.py:67-137`）：
   - HOCON 配置多行输入 + "Lint 配置" 主按钮 → `POST /api/conflint/lint`
     （`config` + `lang` + `report=true`），渲染 markdown 报告；
   - "目录批量 Lint" 折叠区：目录输入（默认 `examples/conflint_demo`）+ 按钮 →
     同端点 `dir` 字段；空输入/坏目录的警告文案与 Gradio 版对等；
   - i18n dict 从 `ui.py:26-61` 原样搬到 i18next；暗色模式走 @shared theme。
4. **REST 挂载核对**：现有 router 经 manifest `api=` 挂载；按触点清单第 4 点
   确认 external 切换后 API 仍可达（必要时在 hub/ui.py 无条件挂载并清 manifest api=，
   与先例一致）。
5. **Cutover**：manifest `external=True`、`render=""`；删除 `config_lint/ui.py`；
   `seatunnel-agent ui --build` 构建验证页面可用；after 截图（zh/en、亮/暗）。

## 验证

- ruff check src tests、mypy、定向测试（config_lint 相关 + test_registry）
- `cd frontend && npm run lint --workspace config_lint && npm run build --workspace config_lint`
- 手动/脚本截图对比 before/after

## 不做

- 不改 linter.py/report.py 后端逻辑；不加新功能；不动其他页面。
