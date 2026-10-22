# 01: 新建 frontend/secret_scan workspace 并切换 manifest

**What to build:** 对标 `frontend/pii_scan` 骨架新建 `frontend/secret_scan/`（App.tsx 文本扫描表单 + 结果区，api.ts 调 `POST /api/secretscan/scan`，i18n.ts 从 `ui.py` `_I18N` 逐字平移，复用 @shared theme/card/lang.ts）；`frontend/package.json` workspaces 加 `secret_scan`；vite `base: '/secretscan/'`、dev proxy `/api/secretscan`。manifest 改 `external=True, render=""`。目录扫描按方案 A：页面提示用 CLI，不加新端点。

**Blocked by:** 无

**Status:** ready-for-agent

- [ ] workspace 构建通过（`npm run build --workspace secret_scan`）
- [ ] 文本扫描命中规则并显示脱敏预览（走现有 REST）
- [ ] 中英文随 st-lang cookie 切换，i18n 逐字平移
- [ ] manifest `external=True, render=""`，页面经 hub 静态挂载可访问
- [ ] i18n parity 测试（照 test_datacompare_i18n.py 模式）
- [ ] ruff / mypy / 定向 pytest 通过
