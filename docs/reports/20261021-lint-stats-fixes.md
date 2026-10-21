# 批次结果报告:既有问题修复·text2sql lint + sql_review stats 页测(2026-10-21)

## 批准依据

> 用户以 `/to-spec` 原话圈选:"2. text2sql src 的 6 个既有 lint 错误(另票) 3. test_sql_review_page stats 测试的环境相关既有失败(另票)解决掉",随后 `/to-tickets`、`/implement-spec` 启动;分支沿用 plat 直提。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | 票01:text2sql lint 归零——BoardsView ×4 / SubscriptionsView ×1 的 any 换真实类型(api.ts 提取 BoardRenderResult、runSubscription 补 error 字段);MetricsView 的 rules-of-hooks 系误命名触发(useMetric 并非 Hook),重命名 applyMetric;ChatPanel exhaustive-deps 警告补依赖 | frontend/text2sql/src/ ×5 文件 +21/−10 | e4daf0c |
| 中 | 票02:stats 页测隔离——fixture 设 SQLREVIEW_LOG_DIR(rlog.py:32)指向 tmp 空目录,读取端与写入端对称隔离;断言不动 | tests/test_sql_review_page.py +3/−1 | ef0b764 |

## 验证结果

```
npm run lint --workspace text2sql  -> 0 errors 0 warnings(原 6 errors 1 warning)
npm run build --workspace text2sql -> ✓ built in 8.00s
pytest tests/test_t2s_chat_api.py  -> 9 passed;pytest -m uitest tests/test_t2s_page.py -> 18 passed
pytest -m uitest tests/test_sql_review_page.py -> 9 passed(含原失败的 stats_refresh,本机有真实 review 历史即天然复现环境)
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 109 source files
pytest -q              -> 3286 passed, 1 skipped, 237 deselected
uitest smoke --no-llm  -> PASS 22 · FAIL 0(runs/20261021_102151/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- lint:text2sql 6 errors 1 warning → 0/0,25 个 workspace lint 门禁首次全绿。
- 测试:test_sql_review_page 9/9(此前本机 8/9);全量 pytest 数字不变(3286)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | data_skew src 1 条 react-refresh warning(既有) | C2 票07 | 旧代码 | 无 error | 顺手修或忽略 |
| 低 | chunk >500kB 警告(text2sql/llm_eval/llm_cost 等) | build 输出 | 未 code-split | 体积提示 | 统一 manualChunks 另票 |
| 中 | 紫色 hub 卡片 ×2(orchestrator/issue_triage) | 两 manifest | 既有配置 | 规范违反 | 等用户给色 |

## 未执行的步骤

无。
