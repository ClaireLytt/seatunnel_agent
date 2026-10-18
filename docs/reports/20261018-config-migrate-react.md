# 批次结果报告:config_migrate React 迁移(2026-10-18)

## 批准依据

> 用户以 `/implement-spec` 启动实现(spec:`.scratch/config-migrate-react/spec.md`;此前 grill 轮以 "yes" 确认:React 完整迁移、1:1 对等、同批次退役 Gradio 页、4 票拆分)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:React workspace(frontend/config_migrate,uitest 骨架+@shared 主题)+ /api/config_migrate 单条迁移端点 + hub 挂载 + i18n 平移 + 内置 HOCON 高亮(零新依赖) | frontend/config_migrate/*, agents/data/config_migrate/api.py, hub/ui.py, tests/test_config_migrate_api.py | b531119 |
| 高 | 票 02:批量目录迁移端点与页面折叠区(保留服务器路径语义) | 同上 api.py, App.tsx, api.ts | 3b874f5 |
| 高 | 票 03:manifest external 切换,删 Gradio ui.py(-138 行),触点清理(css/page/catalog/cases/docs,对照 react_migration.md 6-12 条) | manifest.py, hub/css.py, ui_testing/*, cases/migrate.yaml(删) | ac78c8e |
| 中 | 票 04:Playwright 页面测试(等价覆盖退役 MIG1-4 + 语言切换)+ i18n parity | tests/test_config_migrate_page.py, tests/test_config_migrate_i18n.py | 6d23a1e |
| 中 | code-review 修复:bad_dir 错误本地化(400+结构化 detail,前端 t('bad_dir'))、页面测试走 registry.frontend_dist()、TS 死字段删除、微瑕 | api.py, api.ts, App.tsx, tests | fb9d40d |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 115 source files
pytest -q              -> 3154 passed, 1 skipped, 92 deselected in 149.63s
pytest -m uitest tests/test_config_migrate_page.py -> 7 passed in 25.04s
npm run lint --workspace config_migrate -> 通过
npm run build --workspace config_migrate -> ✓ built in 3.21s
uitest smoke (--no-llm) -> PASS 57 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 1 · 耗时 241s
  报告: runs/20261018_161722/report.html
python scripts/check_workflow.py -> 见下(随本报告提交核对)
```

## 前后差异

- 测试:全量 3142 → 3154 passed(+12:API 8、i18n 4;另 uitest 标记页面测试 7 个);uitest smoke 60 → 57(MIG1-4 与 SCR7 退役,等价覆盖移入 tests/test_config_migrate_page.py),FAIL 均为 0。
- UI 截图对比(真浏览器,1280x900):
  - 旧 Gradio 页:`.scratch/config-migrate-react/screenshots/old_en.png`(815563e worktree)
  - 新 React 页:`.scratch/config-migrate-react/screenshots/new_en.png`、`new_zh.png`
  - 功能区 1:1:输入框/Migrate/批量折叠(默认收起)/yaml 输出/报告/中英切换;视觉与其余 React 页一致(engineering-paper,无蓝紫渐变)。
- 代码:Gradio ui.py -138 行、cases/migrate.yaml -53 行;新增 React workspace 与 API。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 批量迁移仍为服务器路径模式,无浏览器上传/打包下载 | spec Out of Scope | 1:1 迁移范围约定 | 远程用户需服务器文件系统访问 | 需要时单独立 spec |
| 低 | App.tsx run/runBatch 存在同形 busy/error 骨架 | code-review Standards 轴 | 量小,保持简单未抽取 | 轻微重复 | 后续页面变更时顺势抽取 |
| 低 | test_datacompare_page.py 仍自拼 dist 路径(存量同病) | code-review Standards 轴 | 存量代码,超本批次范围 | 与 pitfalls 条目不一致 | 下次动该文件时一并改 registry.frontend_dist() |

## 未执行的步骤

- 旧 Gradio 页仅截英文(zh 切换在旧页未截):截图对比目的已达成,未补截。
