# 批次结果报告:localStorage 桥键名收敛(遗留项 2)(2026-10-17)

## 批准依据

> 用户在"20261017-sqlreview-review-fixes-retro.md 遗留清单"呈报后回复:"2"(圈选第 2 项:localStorage 桥键名裸串散布 4 文件)。

## 已完成

| 优先级 | 内容 | 文件 |
| --- | --- | --- |
| 中 | Python 端单一定义点:`TRANSPILE_SQL_KEY`/`DATASKEW_SQL_KEY` + 共用 `pickup_js()`(顺带收敛 transpile/dataskew 两段同形接收 JS 的重复代码) | src/seatunnel_agent/common/bridge.py(新增) |
| 中 | 三处 Python 使用点改引常量:transpile 接收、dataskew 接收、data_comparison 发送 | sql_transpile/ui.py、data_skew/ui.py、data_comparison/ui_cards.py |
| 中 | React 端单一定义点并在 App.tsx 引用 | frontend/shared/src/bridge.ts(新增)、frontend/sql_review/src/App.tsx |
| 中 | 守护测试:双端键名一致 + src/ 内不得再出现裸键名 | tests/test_bridge.py(新增) |

## 验证结果

```
npm run lint --workspace sql_review       -> 通过(eslint src 无输出)
npm run build --workspace sql_review      -> ✓ built in 10.35s
ruff check src tests                      -> All checks passed!
mypy                                      -> Success: no issues found in 103 source files
pytest -q                                 -> 2978 passed, 1 skipped, 99 deselected
pytest -m uitest tests/test_sql_review_page.py -> 4 passed(含 dataskew 桥接用例)
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                                          -> PASS 83 · FAIL 0 · ERROR 0 · SKIP 2 · MANUAL 4 · 耗时 454s
                                             报告: runs/20261017_204331/report.html
python scripts/check_workflow.py          -> 本批提交后执行,输出附于对话
```

(注:smoke 为上一批 fix/chore 提交后触发、在本批改动前完成的运行——桥接行为本批未变,
键名仅等值替换,且 4 条 Playwright 页测试(含桥接)在本批改动后全绿。)

## 前后差异

- 测试:全量 2976 → 2978 passed(新增 test_bridge.py 两条)。
- 代码:桥键名 7 处裸串 → 双端各 1 处定义;transpile/dataskew 两段 16 行同形 JS → 1 个 `pickup_js()`。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | DIALECTS/DIALECT_NAMES/CHECK_CATALOG_EN/别名表前后端双份 | api.ts、i18n.ts vs prompts.py、linter.py、i18n.py | 未圈选 | 新增方言/类别需双端同改 | 后续加 meta 端点时收敛 |
| 低 | `st_dataskew_conn` cookie 键仍为裸串(1 处,data_comparison/ui_cards.py:693) | 同文件 | 单处使用、非本项范围(本项为 localStorage SQL 桥) | 极小 | 对端迁 React 时一并入 bridge |
| 低 | /transpile、/dataskew 仍为 Gradio | manifest | 不在范围 | 风格不一致 | 按 docs/react_migration.md 迁移 |

## 未执行的步骤

- 无。
