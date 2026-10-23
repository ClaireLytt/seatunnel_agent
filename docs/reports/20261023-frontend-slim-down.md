# 批次结果报告:frontend-slim-down(API 客户端去重 F01–F03)(2026-10-23)

## 批准依据

> 用户通过 `/implement-spec` 指令批准实现 `.scratch/frontend-slim-down/spec.md` 全部票据(01/02/03)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `postStructured` 入 @shared/api,试点迁移 dag_check、metric_diff | frontend/shared/src/api.ts 等 | 8af0e6d |
| 高 | 迁移 6 个结构化错误工作区(pii_scan、schema_drift、sql_fmt、sql_transpile、config_lint、config_migrate) | frontend/*/src/api.ts | 2bc543a |
| 中 | text2sql、seatunnel 全部普通 JSON 调用改用共享 fetchJson(删除本地 `j` 辅助与手写 throw) | frontend/text2sql、frontend/seatunnel | 7b551d4 |

净效果:frontend/ 11 文件,+108/−226 行。

**范围调整(票 02)**:原计划 9 个工作区,实际迁移 6 个。change_impact、data_lineage、data_skew 各自定义了语义不同的本地 ApiError(message 取自 `d.message`、带 suggestions 字段),且内部已有单一 request 辅助——强行收敛会改变错误文案,违背"行为不变"约束,按 spec 故事 12 保留并在此记录。

## 验证结果

```
npm run lint/build(shared + 10 个触及工作区) -> 全部 OK
ruff check src tests                 -> All checks passed!
mypy                                 -> Success: no issues found in 106 source files
pytest -q(全量)                    -> 3331 passed, 1 skipped, 242 deselected
pytest 页面测试(试点 2 页)        -> 16 passed
pytest 页面测试(F02 的 6 页)      -> 54 passed
pytest 页面测试(t2s + seatunnel)  -> 4 failed, 19 passed(4 例为批前已存在,见遗留)
python -m …ui_testing run --suite smoke --no-llm -> PASS 16 · FAIL 0(报告 runs/20261023_175400/report.html)
python scripts/check_workflow.py     -> 见提交后输出(报告落盘前"工作区不干净/缺报告"属预期)
```

## 前后差异

- 结构化错误 fetch 块:11 份副本 → 共享 `postStructured` 1 份 + 3 份记录在案的语义分叉(grep `then((d) => d.detail` 仅余 change_impact/data_lineage/data_skew + shared 本体)。
- text2sql/seatunnel:手写 `!r.ok → throw` 12 处 → 共享 fetchJson;`stopChat`(text2sql)保留原样(有意忽略错误)。
- 页面行为:试点/F02 共 70 例页面测试全绿;uitest smoke 16/16 PASS,与批前一致。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | test_t2s_page.py 4 例批前即失败(connect 显示 Internal Server Error) | stash 后同样 4 failed;服务端日志 `RuntimeError: API_KEY is not set` | 本机 .env 缺 API_KEY,connect 后端 500 | 本机无法全绿 t2s 页面测试(CI 有 key 应不受影响) | 配置 .env 后复跑确认 |
| 低 | change_impact/data_lineage/data_skew 各留一份本地错误解析 | 上文 grep 输出 | 语义分叉(message/suggestions) | 三份相似但不相同的实现 | 如要收敛需先统一错误契约(后端+catch 站点),另立 spec |

## 未执行的步骤

- change_impact/data_lineage/data_skew 的迁移:未执行(语义分叉,见范围调整)。
- /implement-spec 模板的 worktree/并行子代理/集成分支/draft PR 流程:未执行(CLAUDE.md 禁止,串行于 dev)。
